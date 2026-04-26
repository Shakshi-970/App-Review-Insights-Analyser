from google_play_scraper import reviews, Sort
from datetime import datetime, timedelta
from typing import List, Optional
import os
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
            # Some setups inject a broken local proxy into env vars; temporarily disable.
            _proxy_keys = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")
            _saved = {k: os.environ.get(k) for k in _proxy_keys}
            for k in _proxy_keys:
                os.environ.pop(k, None)
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
        finally:
            # Restore env vars
            for k, v in _saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        raw_reviews = []
        for r in result:
            review_date = r['at']
            if review_date.replace(tzinfo=None) < cutoff_date:
                break

            review_text = r['content']
            if len(review_text.strip()) < settings.MIN_REVIEW_LENGTH:
                continue

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
