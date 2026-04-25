import json
import os
from datetime import datetime

from src.phase0_foundations.models import PulseReport, Theme
from src.phase4_renderer.doc_renderer import DocRenderer
from src.phase4_renderer.email_renderer import EmailRenderer

THEMES_PATH  = "src/phase3_summarization/data/themes_Groww.json"
OUTPUT_DIR   = "src/phase4_renderer/data"
DOC_LINK     = "https://docs.google.com/document/d/GROWW_WEEKLY_PULSE_DOC_STUB"

def main():
    print("=== Phase 4: Renderer Run (Target: Groww) ===\n")

    # 1. Load themes from Phase 3 output
    if not os.path.exists(THEMES_PATH):
        print(f"Error: themes file not found at {THEMES_PATH}")
        return

    with open(THEMES_PATH, "r", encoding="utf-8") as f:
        raw_themes = json.load(f)

    themes = [Theme(**t) for t in raw_themes]
    print(f"Loaded {len(themes)} themes from Phase 3.")

    # 2. Build PulseReport
    report = PulseReport(
        product      = "Groww",
        iso_week     = "2026-W17",
        period       = "Last 104 weeks",
        review_count = 1818,
        themes       = themes,
        generated_at = datetime.now(),
    )
    print(f"Built PulseReport: {report.product} / {report.iso_week} / {report.review_count} reviews\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 3. Doc renderer → Markdown
    doc_renderer = DocRenderer()
    markdown     = doc_renderer.render(report)
    md_path      = os.path.join(OUTPUT_DIR, "report_Groww.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    print(f"[OK] Markdown report saved  -> {md_path}")

    # 4. Email renderer → HTML
    email_renderer = EmailRenderer()
    html           = email_renderer.render(report, doc_link=DOC_LINK)
    html_path      = os.path.join(OUTPUT_DIR, "teaser_Groww.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK] HTML teaser saved      -> {html_path}")

    print("\nPhase 4 complete.")

if __name__ == "__main__":
    main()
