import feedparser
import requests
from datetime import datetime, timedelta
from typing import List
from src.phase0_foundations.models import Review, CleanReview
from src.phase0_foundations.config import settings

from src.phase1_ingestion.pii_scrubber import ReviewScrubber

class AppStoreScraper:
    def __init__(self):
        self.base_url = "https://itunes.apple.com/in/rss/customerreviews/id={app_id}/sortby=mostrecent/xml"
        self.scrubber = ReviewScrubber()

    def fetch_reviews(self, product_name: str) -> List[CleanReview]:
        app_id = settings.APP_STORE_IDS.get(product_name)
        if not app_id:
            print(f"No App Store ID found for {product_name}")
            return []

        url = self.base_url.format(app_id=app_id)
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to fetch App Store reviews for {product_name}: {response.status_code}")
            return []

        feed = feedparser.parse(response.content)
        raw_reviews = []
        
        # Calculate rolling window
        cutoff_date = datetime.now() - timedelta(weeks=settings.ROLLING_WINDOW_WEEKS)

        for entry in feed.entries:
            if "content" not in entry or "updated" not in entry:
                continue
            
            try:
                review_date = datetime.fromisoformat(entry.updated)
                if review_date.replace(tzinfo=None) < cutoff_date:
                    continue

                review = Review(
                    review_id=entry.id,
                    product=product_name,
                    store="appstore",
                    rating=int(entry.get("im_rating", 0)),
                    title=None,
                    text=entry.content[0].value if entry.content else "",
                    date=review_date,
                    language="en"
                )
                raw_reviews.append(review)
            except Exception as e:
                print(f"Error parsing entry {entry.id}: {e}")
                continue

        return self.scrubber.process_batch(raw_reviews)
