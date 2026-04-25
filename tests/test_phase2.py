import unittest
import numpy as np
from datetime import datetime
from src.phase0_foundations.models import CleanReview
from src.phase2_clustering.embedder import Embedder
from src.phase2_clustering.clusterer import Clusterer


def _make_review(i: int, text: str) -> CleanReview:
    return CleanReview(
        review_id=f"r{i}",
        product="Groww",
        store="playstore",
        rating=3,
        text=text,
        original_text=text,
        date=datetime.now(),
    )


class TestEmbedder(unittest.TestCase):
    def test_output_shape(self):
        emb = Embedder()
        texts = ["Good trading app", "App crashes often", "Great customer support"]
        result = emb.embed(texts)
        self.assertEqual(result.shape, (3, 384))
        self.assertEqual(result.dtype, np.float32)

    def test_empty_input(self):
        emb = Embedder()
        result = emb.embed([])
        self.assertEqual(result.shape, (0, 384))


class TestClusterer(unittest.TestCase):
    def _make_diverse_reviews(self):
        texts = (
            ["App crashes every time I open it"] * 8
            + ["Great investment platform, easy to use"] * 8
            + ["Customer support is very slow to respond"] * 8
            + ["The UI is confusing and hard to navigate"] * 7
        )
        return [_make_review(i, t) for i, t in enumerate(texts)]

    def test_produces_clusters_for_diverse_input(self):
        reviews = self._make_diverse_reviews()
        emb = Embedder()
        embeddings = emb.embed([r.text for r in reviews])
        clusters = Clusterer().cluster(embeddings, reviews)
        self.assertGreaterEqual(len(clusters), 2)

    def test_centroid_indices_within_bounds(self):
        reviews = self._make_diverse_reviews()
        emb = Embedder()
        embeddings = emb.embed([r.text for r in reviews])
        clusters = Clusterer().cluster(embeddings, reviews)
        for c in clusters:
            self.assertLessEqual(len(c.centroid_indices), 10)
            for idx in c.centroid_indices:
                self.assertGreaterEqual(idx, 0)
                self.assertLess(idx, len(c.reviews))

    def test_all_reviews_accounted_for(self):
        reviews = self._make_diverse_reviews()
        emb = Embedder()
        embeddings = emb.embed([r.text for r in reviews])
        clusters = Clusterer().cluster(embeddings, reviews)
        total = sum(len(c.reviews) for c in clusters)
        self.assertEqual(total, len(reviews))

    def test_tiny_input_returns_single_cluster(self):
        reviews = [_make_review(i, "Some feedback") for i in range(3)]
        emb = Embedder()
        embeddings = emb.embed([r.text for r in reviews])
        clusters = Clusterer().cluster(embeddings, reviews)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0].label, "General Feedback")


if __name__ == "__main__":
    unittest.main()
