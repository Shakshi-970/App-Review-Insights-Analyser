import uuid
from datetime import datetime
from typing import List, Optional

from src.phase0_foundations.config import settings
from src.phase0_foundations.models import CleanReview, Cluster, Theme, PulseReport, RenderedReport, RunRecord
from src.phase0_foundations.run_log import RunLog

from src.phase1_ingestion.appstore_scraper import AppStoreScraper
from src.phase1_ingestion.playstore_scraper import PlayStoreScraper

from src.phase2_clustering.embedder import Embedder
from src.phase2_clustering.clusterer import Clusterer

from src.phase3_summarization.synthesizer import Synthesizer

from src.phase4_renderer.doc_renderer import DocRenderer
from src.phase4_renderer.email_renderer import EmailRenderer

from src.phase5_docs_mcp.docs_client import DocsClient
from src.phase6_gmail_mcp.gmail_client import GmailClient

class ProductReviewAgent:
    """
    Orchestrates the end-to-end flow from scraping to delivery.
    """

    def __init__(self):
        self.logger = RunLog()
        self.embedder = Embedder()
        self.clusterer = Clusterer()
        self.synthesizer = Synthesizer()
        self.doc_renderer = DocRenderer()
        self.email_renderer = EmailRenderer()
        self.docs_client = DocsClient()
        self.gmail_client = GmailClient()

    def run_pulse(self, product: str, iso_week: Optional[str] = None):
        """
        Executes a single pulse run for a product and week.
        """
        if not iso_week:
            # Current ISO week
            iso_week = datetime.now().strftime("%G-W%V")

        run_id = str(uuid.uuid4())
        print(f"[*] Starting run {run_id} for {product} ({iso_week})")

        # 0. Check if already succeeded
        if self.logger.exists(product, iso_week):
            print(f"[!] Run for {product} {iso_week} already succeeded. Skipping.")
            return

        run_record = RunRecord(
            run_id=run_id,
            product=product,
            iso_week=iso_week,
            status="failed", # default to failed until success
            started_at=datetime.now()
        )
        
        # Log the start of the run
        self.logger.create_run(run_record)

        try:
            # 1. Ingestion
            print("[1/7] Ingesting reviews...")
            reviews = self._ingest(product)
            run_record.review_count = len(reviews)
            if not reviews:
                print("[!] No reviews found. Skipping.")
                run_record.status = "skipped"
                self.logger.update_run(run_record)
                return

            # 2. Clustering
            print(f"[2/7] Clustering {len(reviews)} reviews...")
            embeddings = self.embedder.embed([r.text for r in reviews])
            clusters = self.clusterer.cluster(embeddings, reviews)

            # 3. Summarization
            print(f"[3/7] Summarizing {len(clusters)} clusters...")
            themes = self.synthesizer.synthesize_clusters(product, clusters)
            
            report = PulseReport(
                product=product,
                iso_week=iso_week,
                period=f"Last {settings.ROLLING_WINDOW_WEEKS} weeks",
                review_count=len(reviews),
                themes=themes
            )

            # 4. Rendering
            print("[4/7] Rendering reports...")
            doc_markdown = self.doc_renderer.render(report)
            anchor = self.doc_renderer.generate_anchor(product, iso_week)
            # Email needs a placeholder link for now, will update if possible
            email_html = self.email_renderer.render(report)

            # 5. Docs Delivery
            print("[5/7] Appending to Google Doc...")
            # We need a document_id. For now, we'll assume it's in a mapping or env
            # In a real app, this might be looked up from a DB or config
            doc_id = "YOUR_GOOGLE_DOC_ID_HERE" # Placeholder
            doc_result = self.docs_client.run_append_report(doc_id, doc_markdown, anchor)
            run_record.doc_id = doc_id
            
            # 6. Gmail Delivery
            print("[6/7] Sending Gmail notification...")
            recipient = "stakeholders@example.com" # Placeholder
            gmail_result = self.gmail_client.run_send_teaser(
                recipient, 
                f"Pulse Report: {product} {iso_week}",
                email_html
            )
            run_record.email_message_id = gmail_result.get("message_id")

            # 7. Finalize
            run_record.status = "success"
            run_record.completed_at = datetime.now()
            print(f"[*] Run {run_id} completed successfully.")

        except Exception as e:
            print(f"[ERROR] Run {run_id} failed: {e}")
            run_record.status = "failed"
            # Optional: capture more error info
            raise
        finally:
            self.logger.update_run(run_record)

    def _ingest(self, product: str) -> List[CleanReview]:
        """Combines App Store and Play Store reviews. Scrubbing happens inside scrapers."""
        app_scraper = AppStoreScraper()
        play_scraper = PlayStoreScraper()
        
        # Scrapers return List[CleanReview]
        raw_app = app_scraper.fetch_reviews(product)
        raw_play = play_scraper.fetch_reviews(product)
        
        return raw_app + raw_play

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Product Review Pulse Agent")
    parser.add_argument("--product", required=True, help="Product name (e.g. Groww)")
    parser.add_argument("--week", help="ISO Week (e.g. 2026-W17)")
    args = parser.parse_args()

    agent = ProductReviewAgent()
    agent.run_pulse(args.product, args.week)
