"""
Phase 5 & 6 runner: writes the Groww weekly pulse to Google Docs, then
sends the HTML teaser via Gmail.
"""
import json
import logging
import os
from datetime import datetime

from src.phase0_foundations.config import settings
from src.phase0_foundations.models import PulseReport, Theme
from src.phase4_renderer.email_renderer import EmailRenderer
from src.phase5_docs_mcp.docs_client import DocsClient
from src.phase6_gmail_mcp.gmail_client import GmailClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("run_phase5_6")

THEMES_PATH = "src/phase3_summarization/data/themes_Groww.json"


def load_report() -> PulseReport:
    with open(THEMES_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    themes = [Theme(**t) for t in raw]
    return PulseReport(
        product      = "Groww",
        iso_week     = "2026-W17",
        period       = "Last 104 weeks",
        review_count = 1818,
        themes       = themes,
        generated_at = datetime.now(),
    )


def main():
    print("=== Phase 5 + 6: Docs MCP + Gmail MCP (Target: Groww) ===\n")

    # ── 0. Validate config ───────────────────────────────────────────────────
    doc_id    = settings.GOOGLE_DOCS_ID
    recipient = settings.RECIPIENT_EMAIL

    if not doc_id:
        print("ERROR: GOOGLE_DOCS_ID not set in .env"); return
    if not recipient:
        print("ERROR: RECIPIENT_EMAIL not set in .env"); return

    print(f"  Doc ID        : {doc_id}")
    print(f"  Recipient     : {recipient}")
    print(f"  Send mode     : {settings.SEND_MODE}\n")

    # ── 1. Build report objects ──────────────────────────────────────────────
    report = load_report()
    anchor = f"pulse-{report.product.lower()}-{report.iso_week.lower()}"
    print(f"[1] Report built — {len(report.themes)} themes, anchor='{anchor}'")

    # ── 2. Phase 5: Google Docs ──────────────────────────────────────────────
    docs_client = DocsClient()

    print("\n[2a] Clearing Google Doc ...")
    clear_result = docs_client.run_clear_document(doc_id)
    print(f"     Clear result : {clear_result.get('status', clear_result)}")

    print("[2b] Writing report to Google Doc ...")
    docs_result = docs_client.run_append_report(doc_id, report, anchor)
    print(f"     Write result : {docs_result.get('status', docs_result)}")
    if docs_result.get("status") == "error":
        print(f"     Error detail : {docs_result.get('detail')}")

    if docs_result.get("status") not in ("success", "skipped"):
        print("ERROR: failed to write to Google Doc. Aborting.")
        print(docs_result)
        return

    doc_url = docs_result.get("doc_url", f"https://docs.google.com/document/d/{doc_id}")
    print(f"     Doc URL      : {doc_url}")

    # ── 3. Phase 6: Gmail ────────────────────────────────────────────────────
    email_html = EmailRenderer().render(report, doc_link=doc_url)

    subject = f"Weekly Pulse: {report.product} | {report.iso_week}"

    print(f"\n[3] Sending email teaser to {recipient} ...")
    gmail_client  = GmailClient()
    gmail_result  = gmail_client.run_send_teaser(recipient, subject, email_html)
    print(f"    Gmail result : {gmail_result.get('status', gmail_result)}")

    # ── 4. Save HTML teaser locally ──────────────────────────────────────────
    out_dir = "src/phase4_renderer/data"
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "teaser_Groww.html"), "w", encoding="utf-8") as f:
        f.write(email_html)

    print("\n[4] Local artefacts saved:")
    print("    src/phase4_renderer/data/teaser_Groww.html")

    print("\nPhase 5 + 6 complete.")


if __name__ == "__main__":
    main()
