import unittest
from datetime import datetime
from src.phase0_foundations.models import Review
from src.phase1_ingestion.pii_scrubber import ReviewScrubber

class TestPhase1(unittest.TestCase):
    def setUp(self):
        self.scrubber = ReviewScrubber(min_word_count=4)

    def test_pii_scrubbing(self):
        review = Review(
            review_id="r1",
            product="Groww",
            store="playstore",
            rating=5,
            text="Contact me at test@example.com or call 9876543210. This is a great app.",
            date=datetime.now()
        )
        cleaned = self.scrubber.process_review(review)
        self.assertIsNotNone(cleaned)
        self.assertIn("[EMAIL]", cleaned.text)
        self.assertIn("[PHONE]", cleaned.text)
        self.assertNotIn("test@example.com", cleaned.text)

    def test_emoji_filter(self):
        # Review with emoji should be filtered out
        review = Review(
            review_id="r2",
            product="Groww",
            store="playstore",
            rating=5,
            text="Love this app! 😊 Best for investing.",
            date=datetime.now()
        )
        cleaned = self.scrubber.process_review(review)
        self.assertIsNone(cleaned)

    def test_word_count_filter(self):
        # Review with < 4 words should be filtered out
        review = Review(
            review_id="r3",
            product="Groww",
            store="playstore",
            rating=1,
            text="Bad app really.",
            date=datetime.now()
        )
        cleaned = self.scrubber.process_review(review)
        self.assertIsNone(cleaned)

    def test_language_filter(self):
        # Review in Hindi (translated) or other language should be filtered out
        # "नमस्ते यह एक अच्छा ऐप है" (Namaste this is a good app)
        review = Review(
            review_id="r4",
            product="Groww",
            store="playstore",
            rating=5,
            text="नमस्ते यह एक अच्छा ऐप है",
            date=datetime.now()
        )
        cleaned = self.scrubber.process_review(review)
        self.assertIsNone(cleaned)

    def test_valid_review(self):
        review = Review(
            review_id="r5",
            product="Groww",
            store="playstore",
            rating=5,
            text="This is a very helpful app for stock market investing.",
            date=datetime.now()
        )
        cleaned = self.scrubber.process_review(review)
        self.assertIsNotNone(cleaned)
        self.assertEqual(cleaned.text, review.text)

if __name__ == "__main__":
    unittest.main()
