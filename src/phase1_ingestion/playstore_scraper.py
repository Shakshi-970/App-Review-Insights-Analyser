from google_play_scraper import reviews, Sort
from datetime import datetime, timedelta
from typing import List, Optional
from src.phase0_foundations.models import Review, CleanReview
from src.phase0_foundations.config import settings

from src.phase1_ingestion.pii_scrubber import ReviewScrubber

class PlayStoreScraper:
    def __init__(self):
        self.scrubber = ReviewScrubber()

    def fetch_reviews(self, product_name: str, count: Optional[int] = None) -> List[CleanReview]:
        if count is None:
            count = settings.REVIEWS_TO_SCRAPE
        app_id = settings.PLAY_STORE_IDS.get(product_name)
        if not app_id:
            print(f"No Play Store ID found for {product_name}")
            return []

        # Calculate rolling window
        cutoff_date = datetime.now() - timedelta(weeks=settings.ROLLING_WINDOW_WEEKS)

        try:
            result, _ = reviews(
                app_id,
                lang='en',
                country='in',
                sort=Sort.NEWEST,
                count=count
            )
        except Exception as e:
            print(f"Failed to fetch Play Store reviews for {product_name}: {e}")
            return []

        raw_reviews = []
        for r in result:
            review_date = r['at']
            if review_date.replace(tzinfo=None) < cutoff_date:
                break

            review_text = r['content']
            review = Review(
                review_id=r['reviewId'],
                product=product_name,
                store="playstore",
                rating=r['score'],
                title=None,
                text=review_text,
                date=review_date,
                language="en"
            )
            raw_reviews.append(review)

        return self.scrubber.process_batch(raw_reviews)
