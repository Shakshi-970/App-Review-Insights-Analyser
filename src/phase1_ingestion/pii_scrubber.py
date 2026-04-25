import re
import emoji
from langdetect import detect, DetectorFactory
from typing import Optional, List
from src.phase0_foundations.models import Review, CleanReview

# Ensure consistent results for language detection
DetectorFactory.seed = 0

class ReviewScrubber:
    """
    Handles PII scrubbing and content filtering (emojis, language, word count).
    """
    def __init__(self, min_word_count: int = 2, target_lang: str = "en"):
        self.min_word_count = min_word_count
        self.target_lang = target_lang
        # PII patterns
        self.email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        self.phone_pattern = re.compile(r'\b\d{10}\b|\+\d{1,3}\d{10}\b') # Simple 10-digit or intl format
        self.aadhaar_pattern = re.compile(r'\b\d{4}\s\d{4}\s\d{4}\b') # Aadhaar-like format

    def has_emoji(self, text: str) -> bool:
        """Check if text contains any emojis."""
        return emoji.emoji_count(text) > 0

    def is_target_language(self, text: str) -> bool:
        """Check if text is in the target language (default English)."""
        try:
            return detect(text) == self.target_lang
        except:
            return False

    def get_word_count(self, text: str) -> int:
        """Get the number of words in the text."""
        return len(text.split())

    def scrub_pii(self, text: str) -> str:
        """Redact sensitive information from text."""
        text = self.email_pattern.sub("[EMAIL]", text)
        text = self.phone_pattern.sub("[PHONE]", text)
        text = self.aadhaar_pattern.sub("[ID]", text)
        return text

    def process_review(self, review: Review) -> Optional[CleanReview]:
        """
        Apply filters and scrub PII. 
        Returns None if the review should be removed.
        """
        text = review.text.strip()

        # Filter: Min word count
        if self.get_word_count(text) < self.min_word_count:
            return None

        # Filter: Emojis - DISABLED
        # if self.has_emoji(text):
        #     return None

        # Filter: Language (User requested removal)
        if not self.is_target_language(text):
            return None

        # Scrub PII
        scrubbed_text = self.scrub_pii(text)

        # Build CleanReview data
        data = review.model_dump()
        data.update({
            "original_text": text,
            "text": scrubbed_text,
            "is_pii_scrubbed": True
        })

        return CleanReview(**data)

    def process_batch(self, reviews: List[Review]) -> List[CleanReview]:
        """Process a list of reviews and filter out invalid ones."""
        cleaned_reviews = []
        for r in reviews:
            processed = self.process_review(r)
            if processed:
                cleaned_reviews.append(processed)
        return cleaned_reviews
