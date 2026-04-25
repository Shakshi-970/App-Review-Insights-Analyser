"""
Phase 7 — Orchestration Agent

LLM-driven loop using Groq tool calling.  The agent coordinates all six
pipeline phases in sequence; data flows through in-memory state between
tool calls rather than being serialised into LLM arguments.

Usage:
    python -m src.phase7_orchestration.agent --product Groww --week 2026-W17
    python -m src.phase7_orchestration.agent --product Groww --backfill
"""

import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from groq import Groq, RateLimitError

from src.phase0_foundations.config import settings
from src.phase0_foundations.models import PulseReport, RunRecord
from src.phase0_foundations.run_log import RunLog

from src.phase1_ingestion.appstore_scraper import AppStoreScraper
from src.phase1_ingestion.playstore_scraper import PlayStoreScraper

from src.phase2_clustering.clusterer import Clusterer
from src.phase2_clustering.embedder import Embedder

from src.phase3_summarization.synthesizer import Synthesizer

from src.phase4_renderer.doc_renderer import DocRenderer
from src.phase4_renderer.email_renderer import EmailRenderer

from src.phase5_docs_mcp.docs_client import DocsClient
from src.phase6_gmail_mcp.gmail_client import GmailClient

from src.phase7_orchestration.tool_registry import TOOL_SCHEMAS

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
_TRANSIENT = (RateLimitError, ConnectionError, TimeoutError, OSError)

_SYSTEM_PROMPT = (
    "You are an orchestration agent for a product-review pulse pipeline. "
    "Call the six tools in order to complete the full run:\n"
    "1. scrape_reviews\n"
    "2. cluster_reviews\n"
    "3. summarize_clusters\n"
    "4. render_report\n"
    "5. publish_to_docs\n"
    "6. send_email\n\n"
    "After all tools succeed, reply with a one-sentence confirmation. "
    "If a tool returns an error, stop immediately and report the failure."
)


class ProductReviewAgent:
    def __init__(self):
        self._run_log = RunLog()
        self._groq = Groq(api_key=settings.GROQ_API_KEY)
        self._embedder = Embedder()
        self._clusterer = Clusterer()
        self._synthesizer = Synthesizer()
        self._doc_renderer = DocRenderer()
        self._email_renderer = EmailRenderer()
        self._docs_client = DocsClient()
        self._gmail_client = GmailClient()
        self._state: Dict[str, Any] = {}

    # ── public API ─────────────────────────────────────────────────────────────

    def run_pulse(self, product: str, iso_week: Optional[str] = None) -> RunRecord:
        if not iso_week:
            iso_week = datetime.now().strftime("%G-W%V")

        if self._run_log.exists(product, iso_week):
            logger.info("Run for %s %s already succeeded — skipping.", product, iso_week)
            return self._run_log.get_run(product, iso_week)

        run_id = str(uuid.uuid4())
        run_record = RunRecord(
            run_id=run_id,
            product=product,
            iso_week=iso_week,
            status="failed",
            started_at=datetime.now(),
        )
        self._run_log.create_run(run_record)
        self._state = {}

        try:
            self._agent_loop(product, iso_week, run_record)
            run_record.status = "success"
            run_record.completed_at = datetime.now()
            run_record.token_usage = self._synthesizer.total_tokens_used
            print(f"[*] Run {run_id} completed successfully.")
        except Exception as e:
            logger.error("Run %s failed: %s", run_id, e)
            run_record.status = "failed"
            raise
        finally:
            self._run_log.update_run(run_record)

        return run_record

    # ── agent loop ─────────────────────────────────────────────────────────────

    def _agent_loop(self, product: str, iso_week: str, run_record: RunRecord):
        messages: List[Dict] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Run the full pulse pipeline for product='{product}', "
                    f"iso_week='{iso_week}'."
                ),
            },
        ]

        while True:
            response = self._groq.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                temperature=0,
            )
            msg = response.choices[0].message

            # Append assistant turn
            assistant_entry: Dict[str, Any] = {"role": "assistant", "content": msg.content}
            if msg.tool_calls:
                assistant_entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(assistant_entry)

            if not msg.tool_calls:
                logger.info("Agent loop finished: %s", msg.content)
                break

            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments or "{}")
                logger.info("Tool call: %s %s", name, args)

                try:
                    result = self._with_retry(self._execute_tool, name, args, run_record)
                except Exception as e:
                    result = {"status": "error", "message": str(e)}
                    logger.error("Tool %s raised: %s", name, e)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )

                if result.get("status") == "error":
                    raise RuntimeError(
                        f"Tool '{name}' failed: {result.get('message', result)}"
                    )

    # ── retry wrapper ──────────────────────────────────────────────────────────

    def _with_retry(self, fn, *args):
        last_exc: Exception = RuntimeError("no attempts made")
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return fn(*args)
            except _TRANSIENT as exc:
                last_exc = exc
                wait = 2 ** attempt
                logger.warning(
                    "Transient error (attempt %d/%d): %s. Retrying in %ds.",
                    attempt, MAX_RETRIES, exc, wait,
                )
                time.sleep(wait)
        raise last_exc

    # ── tool dispatcher ────────────────────────────────────────────────────────

    def _execute_tool(self, name: str, args: dict, run_record: RunRecord) -> dict:
        dispatch = {
            "scrape_reviews": lambda: self._tool_scrape(
                args["product"], args["iso_week"], run_record
            ),
            "cluster_reviews": self._tool_cluster,
            "summarize_clusters": lambda: self._tool_summarize(run_record),
            "render_report": lambda: self._tool_render(run_record),
            "publish_to_docs": lambda: self._tool_publish(run_record),
            "send_email": lambda: self._tool_email(run_record),
        }
        handler = dispatch.get(name)
        if handler is None:
            return {"status": "error", "message": f"Unknown tool: {name}"}
        return handler()

    # ── individual tool implementations ───────────────────────────────────────

    def _tool_scrape(self, product: str, iso_week: str, run_record: RunRecord) -> dict:
        print(f"[1/6] Scraping reviews for {product} ({iso_week})...")
        reviews = AppStoreScraper().fetch_reviews(product) + PlayStoreScraper().fetch_reviews(product)
        if not reviews:
            return {"status": "error", "message": f"No reviews found for {product}"}
        self._state["reviews"] = reviews
        run_record.review_count = len(reviews)
        print(f"      {len(reviews)} reviews collected.")
        return {"status": "ok", "review_count": len(reviews)}

    def _tool_cluster(self) -> dict:
        print("[2/6] Clustering reviews...")
        reviews = self._state["reviews"]
        embeddings = self._embedder.embed([r.text for r in reviews])
        clusters = self._clusterer.cluster(embeddings, reviews)
        self._state["clusters"] = clusters
        print(f"      {len(clusters)} clusters found.")
        return {"status": "ok", "cluster_count": len(clusters)}

    def _tool_summarize(self, run_record: RunRecord) -> dict:
        print("[3/6] Summarizing clusters...")
        themes = self._synthesizer.synthesize_clusters(
            run_record.product, self._state["clusters"]
        )
        self._state["themes"] = themes
        run_record.token_usage = self._synthesizer.total_tokens_used
        print(f"      {len(themes)} themes extracted. Tokens: {run_record.token_usage}")
        return {"status": "ok", "theme_count": len(themes)}

    def _tool_render(self, run_record: RunRecord) -> dict:
        print("[4/6] Rendering report...")
        report = PulseReport(
            product=run_record.product,
            iso_week=run_record.iso_week,
            period=f"Last {settings.ROLLING_WINDOW_WEEKS} weeks",
            review_count=run_record.review_count,
            themes=self._state["themes"],
        )
        self._state["report"] = report
        self._state["anchor"] = self._doc_renderer.generate_anchor(
            run_record.product, run_record.iso_week
        )
        return {"status": "ok", "theme_count": len(report.themes)}

    def _tool_publish(self, run_record: RunRecord) -> dict:
        print("[5/6] Publishing to Google Docs...")
        doc_id = settings.GOOGLE_DOCS_ID
        if not doc_id:
            print("      GOOGLE_DOCS_ID not set — skipping.")
            return {"status": "skipped", "reason": "GOOGLE_DOCS_ID not configured"}

        result = self._docs_client.run_append_report(
            doc_id,
            self._state["report"],
            self._state["anchor"],
        )

        if result.get("status") == "error":
            return {
                "status": "error",
                "message": f"Docs publish failed: {result.get('detail', result)}",
            }

        doc_url = result.get(
            "doc_url", f"https://docs.google.com/document/d/{doc_id}"
        )
        self._state["doc_url"] = doc_url
        run_record.doc_id = doc_id
        run_record.heading_id = self._state["anchor"]
        print(f"      Doc URL: {doc_url}")
        return {"status": result.get("status", "ok"), "doc_url": doc_url}

    def _tool_email(self, run_record: RunRecord) -> dict:
        print("[6/6] Sending teaser email...")
        recipient = settings.RECIPIENT_EMAIL
        if not recipient:
            print("      RECIPIENT_EMAIL not set — skipping.")
            return {"status": "skipped", "reason": "RECIPIENT_EMAIL not configured"}

        doc_url = self._state.get("doc_url", "#")
        report = self._state["report"]
        email_html = self._email_renderer.render(report, doc_url)
        subject = f"Pulse Report: {report.product} {report.iso_week}"

        result = self._gmail_client.run_send_teaser(recipient, subject, email_html)

        if result.get("status") == "error":
            return {
                "status": "error",
                "message": f"Email failed: {result.get('message', result)}",
            }

        run_record.email_message_id = result.get("message_id") or result.get("to")
        print(f"      Email sent to {recipient}.")
        return {"status": result.get("status", "ok"), "recipient": recipient}


# ── backfill helper ────────────────────────────────────────────────────────────

def _rolling_weeks(window: int) -> List[str]:
    """ISO week strings for the last *window* weeks, oldest first."""
    today = datetime.now()
    return [
        (today - timedelta(weeks=i)).strftime("%G-W%V")
        for i in range(window - 1, -1, -1)
    ]


# ── CLI entry point ────────────────────────────────────────────────────────────

def main():
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Product Review Pulse Agent")
    parser.add_argument("--product", required=True, help="Product name, e.g. Groww")
    parser.add_argument(
        "--week", help="ISO week to run, e.g. 2026-W17 (default: current week)"
    )
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="Run for all missing weeks in the rolling window",
    )
    args = parser.parse_args()

    agent = ProductReviewAgent()

    if args.backfill:
        weeks = _rolling_weeks(settings.ROLLING_WINDOW_WEEKS)
        missing = [w for w in weeks if not agent._run_log.exists(args.product, w)]
        print(f"Backfill: {len(missing)} missing week(s) for {args.product}")
        for week in missing:
            print(f"\n=== {args.product} {week} ===")
            try:
                agent.run_pulse(args.product, week)
            except Exception as exc:
                logger.error("Backfill failed for %s %s: %s", args.product, week, exc)
    else:
        agent.run_pulse(args.product, args.week)


if __name__ == "__main__":
    main()
