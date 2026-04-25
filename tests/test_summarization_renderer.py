import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.phase0_foundations.models import CleanReview, Cluster, Theme, PulseReport
from src.phase3_summarization.synthesizer import Synthesizer
from src.phase3_summarization.quote_validator import QuoteValidator
from src.phase4_renderer.doc_renderer import DocRenderer
from src.phase4_renderer.email_renderer import EmailRenderer

class TestSummarizationRenderer(unittest.TestCase):

    def setUp(self):
        self.reviews = [
            CleanReview(
                review_id="1", product="Groww", store="appstore", rating=1, 
                text="The app crashes every time I try to login.", 
                date=datetime.now(), original_text="...", is_pii_scrubbed=True
            ),
            CleanReview(
                review_id="2", product="Groww", store="appstore", rating=2, 
                text="Login is very buggy, it takes multiple attempts.", 
                date=datetime.now(), original_text="...", is_pii_scrubbed=True
            ),
            CleanReview(
                review_id="3", product="Groww", store="appstore", rating=5, 
                text="Great app, but the login screen could be better.", 
                date=datetime.now(), original_text="...", is_pii_scrubbed=True
            )
        ]
        self.cluster = Cluster(
            cluster_id=1,
            reviews=self.reviews,
            centroid_indices=[0, 1]
        )

    def test_quote_validator(self):
        validator = QuoteValidator()
        source_texts = [r.text for r in self.reviews]
        
        valid = validator.validate(["app crashes every time", "Login is very buggy"], source_texts)
        self.assertEqual(len(valid), 2)
        
        invalid = validator.validate(["non-existent quote"], source_texts)
        self.assertEqual(len(invalid), 0)

    @patch('src.phase3_summarization.synthesizer.Groq')
    def test_synthesizer(self, mock_groq):
        # Mock LLM response
        mock_client = mock_groq.return_value
        mock_client.chat.completions.create.return_value.choices[0].message.content = """
        {
            "name": "Login Issues",
            "description": "Users are experiencing crashes and bugs during the login process.",
            "quotes": ["The app crashes every time", "Login is very buggy"],
            "action_ideas": ["Fix the login crash", "Improve login stability"]
        }
        """
        
        synth = Synthesizer()
        themes = synth.synthesize_clusters("Groww", [self.cluster])
        
        self.assertEqual(len(themes), 1)
        self.assertEqual(themes[0].name, "Login Issues")
        self.assertEqual(len(themes[0].quotes), 2)

    def test_renderers(self):
        report = PulseReport(
            product="Groww",
            iso_week="2026-W17",
            period="Last 12 weeks",
            review_count=3,
            themes=[
                Theme(
                    name="Login Issues",
                    description="Users are experiencing crashes.",
                    quotes=["The app crashes every time"],
                    action_ideas=["Fix the crash"]
                )
            ]
        )
        
        doc_renderer = DocRenderer()
        markdown = doc_renderer.render(report)
        self.assertIn("## Weekly Pulse — Groww — 2026-W17", markdown)
        self.assertIn("> \"The app crashes every time\"", markdown)
        
        email_renderer = EmailRenderer()
        html = email_renderer.render(report, doc_link="https://docs.google.com/test")
        self.assertIn("Groww — Weekly Review Pulse", html)
        self.assertIn("https://docs.google.com/test", html)

if __name__ == "__main__":
    unittest.main()
