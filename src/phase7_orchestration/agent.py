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

from groq import RateLimitError

from src.phase0_foundations.config import settings
from src.phase0_foundations.models import PulseReport, RunRecord
from src.phase0_foundations.run_log import RunLog

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
_TRANSIENT = (RateLimitError, ConnectionError, TimeoutError, OSError)


class ProductReviewAgent:
    def __init__(self, clear_doc: bool = False, pause_email: bool = False):
        print("[*] Initializing agent (lightweight)...")
        self._run_log = RunLog()
        self._clear_doc = clear_doc
        self._pause_email = pause_email
        self._state: Dict[str, Any] = {}

        # Lazy-loaded — heavy objects deferred until first use
        self._embedder = None
        self._clusterer = None
        self._synthesizer = None
        self._doc_renderer = None
        self._email_renderer = None
        self._docs_client = None
        self._gmail_client = None

    # ── lazy loaders ──────────────────────────────────────────────────────────

    @property
    def embedder(self):
        if self._embedder is None:
            from src.phase2_clustering.embedder import Embedder
            self._embedder = Embedder()
        return self._embedder

    @property
    def clusterer(self):
        if self._clusterer is None:
            from src.phase2_clustering.clusterer import Clusterer
            self._clusterer = Clusterer()
        return self._clusterer

    @property
    def synthesizer(self):
        if self._synthesizer is None:
            from src.phase3_summarization.synthesizer import Synthesizer
            self._synthesizer = Synthesizer()
        return self._synthesizer

    @property
    def doc_renderer(self):
        if self._doc_renderer is None:
            from src.phase4_renderer.doc_renderer import DocRenderer
            self._doc_renderer = DocRenderer()
        return self._doc_renderer

    @property
    def email_renderer(self):
        if self._email_renderer is None:
            from src.phase4_renderer.email_renderer import EmailRenderer
            self._email_renderer = EmailRenderer()
        return self._email_renderer

    @property
    def docs_client(self):
        if self._docs_client is None:
            from src.phase5_docs_mcp.docs_client import DocsClient
            self._docs_client = DocsClient()
        return self._docs_client

    @property
    def gmail_client(self):
        if self._gmail_client is None:
            from src.phase6_gmail_mcp.gmail_client import GmailClient
            self._gmail_client = GmailClient()
        return self._gmail_client

    # ── public API ─────────────────────────────────────────────────────────────

    def run_pulse(self, product: str, iso_week: Optional[str] = None, force: bool = False) -> RunRecord:
        print(f"[*] Pulse Agent starting for {product}...")
        if not iso_week:
            iso_week = datetime.now().strftime("%G-W%V")

        if not force and self._run_log.exists(product, iso_week):
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

            # Output final result as JSON for the portal
            result_data = {
                "type": "result",
                "product": product,
                "week": iso_week,
                "review_count": run_record.review_count,
                "token_usage": run_record.token_usage,
                "doc_url": self._state.get("doc_url"),
                "email_html": self._state.get("email_html"),
                "email_subject": self._state.get("email_subject"),
                "themes": [t.model_dump() for t in self._state.get("themes", [])]
            }
            print(f"\n[RESULT_JSON] {json.dumps(result_data)}")

            # If email was paused, mark as pending_email — NOT success
            if self._pause_email:
                run_record.status = "pending_email"
                run_record.completed_at = datetime.now()
                run_record.token_usage = self.synthesizer.total_tokens_used
                print(f"[*] Run {run_id} awaiting email approval.")
            else:
                run_record.status = "success"
                run_record.completed_at = datetime.now()
                run_record.token_usage = self.synthesizer.total_tokens_used
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
        # Pipeline always runs in fixed order — no LLM needed for routing.
        # This reserves all TPM budget for the synthesizer (the only phase
        # that actually needs an LLM).
        pipeline = [
            ("scrape_reviews",    {"product": product, "iso_week": iso_week}),
            ("cluster_reviews",   {}),
            ("summarize_clusters",{}),
            ("render_report",     {}),
            ("publish_to_docs",   {}),
            ("send_email",        {}),
        ]
        for name, args in pipeline:
            logger.info("Running tool: %s", name)
            t0 = time.time()
            result = self._with_retry(self._execute_tool, name, args, run_record)
            print(f"      [timing] {name} took {time.time() - t0:.1f}s")
            if result.get("status") == "error":
                if name == "send_email":
                    # Email failure is non-fatal — doc was already published
                    print(f"      [!] Email skipped: {result.get('message', 'unknown error')}")
                else:
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
        from concurrent.futures import ThreadPoolExecutor
        from src.phase1_ingestion.appstore_scraper import AppStoreScraper
        from src.phase1_ingestion.playstore_scraper import PlayStoreScraper
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_app  = ex.submit(AppStoreScraper().fetch_reviews, product)
            f_play = ex.submit(PlayStoreScraper().fetch_reviews, product)
            reviews = f_app.result() + f_play.result()
        if not reviews:
            return {"status": "error", "message": f"No reviews found for {product}"}
        self._state["reviews"] = reviews
        run_record.review_count = len(reviews)
        print(f"      {len(reviews)} reviews collected.")
        return {"status": "ok", "review_count": len(reviews)}

    def _tool_cluster(self) -> dict:
        print("[2/6] Clustering reviews...")
        reviews = self._state["reviews"]
        sample_size = settings.CLUSTERING_SAMPLE_SIZE
        if len(reviews) > sample_size:
            import random
            reviews = random.sample(reviews, sample_size)
            print(f"      Sampled {sample_size} of {len(self._state['reviews'])} reviews for clustering.")

        n = len(reviews)
        print(f"      Step 1/3 — Embedding {n} reviews with {self.embedder.MODEL_NAME}...")
        t_embed = time.time()
        embeddings = self.embedder.embed([r.text for r in reviews])
        print(f"      Step 1/3 done — embeddings shape {embeddings.shape} in {time.time() - t_embed:.1f}s.")

        print(f"      Step 2/3 — Running UMAP + HDBSCAN...")
        t_cluster = time.time()
        clusters = self.clusterer.cluster(embeddings, reviews)
        print(f"      Step 2/3 done — {len(clusters)} clusters in {time.time() - t_cluster:.1f}s.")

        self._state["clusters"] = clusters
        sizes = sorted([len(c.reviews) for c in clusters], reverse=True)
        print(f"      Step 3/3 — Cluster sizes: {sizes}")
        return {"status": "ok", "cluster_count": len(clusters)}

    def _tool_summarize(self, run_record: RunRecord) -> dict:
        print("[3/6] Summarizing clusters...")
        themes = self.synthesizer.synthesize_clusters(
            run_record.product, self._state["clusters"]
        )
        self._state["themes"] = themes
        run_record.token_usage = self.synthesizer.total_tokens_used
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
        self._state["anchor"] = self.doc_renderer.generate_anchor(
            run_record.product, run_record.iso_week
        )
        return {"status": "ok", "theme_count": len(report.themes)}

    def _tool_publish(self, run_record: RunRecord) -> dict:
        print("[5/6] Publishing to Google Docs...")
        doc_id = settings.GOOGLE_DOCS_ID
        if not doc_id:
            print("      GOOGLE_DOCS_ID not set — skipping.")
            return {"status": "skipped", "reason": "GOOGLE_DOCS_ID not configured"}

        if self._clear_doc:
            print("      Clearing existing document content...")
            self.docs_client.run_clear_document(doc_id)

        result = self.docs_client.run_append_report(
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
        print("[6/6] Rendering teaser email...")
        recipient = settings.RECIPIENT_EMAIL
        if not recipient:
            print("      RECIPIENT_EMAIL not set — skipping.")
            return {"status": "skipped", "reason": "RECIPIENT_EMAIL not configured"}

        doc_url = self._state.get("doc_url", "#")
        report = self._state["report"]
        email_html = self.email_renderer.render(report, doc_url)
        subject = f"Pulse Report: {report.product} {report.iso_week}"
        
        self._state["email_html"] = email_html
        self._state["email_subject"] = subject

        if getattr(self, "_pause_email", False):
            print("      [!] --pause-email flag set. Email drafted but NOT sent.")
            # Return "paused" status — NOT "ok" — so the portal knows
            # this step is awaiting manual approval
            return {"status": "paused", "recipient": recipient, "draft": True}

        print("      Sending teaser email...")
        result = self.gmail_client.run_send_teaser(recipient, subject, email_html)

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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass idempotency check and re-run even if a successful record exists",
    )
    parser.add_argument(
        "--clear-doc",
        action="store_true",
        help="Clear the Google Doc before appending the new report",
    )
    parser.add_argument(
        "--pause-email",
        action="store_true",
        help="Draft the email but do not send it automatically",
    )
    args = parser.parse_args()

    agent = ProductReviewAgent(clear_doc=args.clear_doc, pause_email=args.pause_email)

    if args.backfill:
        weeks = _rolling_weeks(settings.ROLLING_WINDOW_WEEKS)
        missing = [w for w in weeks if not agent._run_log.exists(args.product, w)]
        print(f"Backfill: {len(missing)} missing week(s) for {args.product}")
        for week in missing:
            print(f"\n=== {args.product} {week} ===")
            try:
                agent.run_pulse(args.product, week, force=args.force)
            except Exception as exc:
                logger.error("Backfill failed for %s %s: %s", args.product, week, exc)
    else:
        agent.run_pulse(args.product, args.week, force=args.force)


if __name__ == "__main__":
    main()
