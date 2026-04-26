import logging
import time

import numpy as np
from typing import List
from umap import UMAP
from sklearn.cluster import HDBSCAN

from src.phase0_foundations.models import CleanReview, Cluster

logger = logging.getLogger(__name__)


class Clusterer:
    """
    Groups clean reviews into thematic clusters.

    Pipeline:
      embeddings (n, 384)
        -> UMAP  (n, n_components)
        -> HDBSCAN labels
        -> List[Cluster] with centroid-closest representatives
    """

    def __init__(
        self,
        umap_n_neighbors: int = 5,
        umap_min_dist: float = 0.1,
        umap_n_components: int = 2,
        hdbscan_min_cluster_size: int = 5,
        top_k_representatives: int = 10,
        random_state: int = 42,
    ):
        self.umap_n_neighbors = umap_n_neighbors
        self.umap_min_dist = umap_min_dist
        self.umap_n_components = umap_n_components
        self.hdbscan_min_cluster_size = hdbscan_min_cluster_size
        self.top_k = top_k_representatives
        self.random_state = random_state

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def cluster(
        self, embeddings: np.ndarray, reviews: List[CleanReview]
    ) -> List[Cluster]:
        """
        Returns List[Cluster]. centroid_indices are LOCAL indices into
        each cluster's own reviews list (use cluster.reviews[i]).
        Noise reviews (-1 label) go into an "Other" bucket.
        """
        n = len(reviews)

        # Edge case: too few reviews to cluster
        if n < self.hdbscan_min_cluster_size:
            print(f"      Too few reviews ({n} < {self.hdbscan_min_cluster_size}) — using single 'General Feedback' cluster.")
            return [
                Cluster(
                    cluster_id=0,
                    label="General Feedback",
                    reviews=reviews,
                    centroid_indices=list(range(n)),
                )
            ]

        # --- UMAP dimensionality reduction ---
        print(f"      UMAP: reducing {n} reviews from {embeddings.shape[1]} -> {self.umap_n_components} dims "
              f"(n_neighbors={min(self.umap_n_neighbors, n-1)})...")
        t0 = time.time()
        reduced = self._reduce(embeddings, n)
        print(f"      UMAP done in {time.time() - t0:.1f}s — output shape {reduced.shape}.")

        # --- HDBSCAN clustering ---
        print(f"      HDBSCAN: clustering {n} points (min_cluster_size={self.hdbscan_min_cluster_size})...")
        t0 = time.time()
        labels = HDBSCAN(
            min_cluster_size=self.hdbscan_min_cluster_size,
            min_samples=1,
        ).fit_predict(reduced)
        n_named = len(set(labels) - {-1})
        n_noise = int((labels == -1).sum())
        print(f"      HDBSCAN done in {time.time() - t0:.1f}s — {n_named} clusters, {n_noise} noise points.")

        return self._build_clusters(embeddings, reviews, labels)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _reduce(self, embeddings: np.ndarray, n: int) -> np.ndarray:
        # Clamp n_neighbors so it never exceeds dataset size
        n_neighbors = min(self.umap_n_neighbors, n - 1)
        n_components = min(self.umap_n_components, n - 1)
        try:
            reducer = UMAP(
                n_neighbors=n_neighbors,
                min_dist=self.umap_min_dist,
                n_components=n_components,
                random_state=self.random_state,
            )
            return reducer.fit_transform(embeddings)
        except Exception as e:
            print(f"      [UMAP fallback] {e} — using raw embeddings.")
            logger.warning("UMAP failed (%s) — falling back to raw embeddings.", e)
            return embeddings

    def _build_clusters(
        self,
        embeddings: np.ndarray,
        reviews: List[CleanReview],
        labels: np.ndarray,
    ) -> List[Cluster]:
        unique_labels = sorted(set(labels.tolist()))
        clusters: List[Cluster] = []
        logger.debug("Building clusters for labels: %s", unique_labels)

        for label in unique_labels:
            mask = labels == label
            idxs = np.where(mask)[0]          # global positions
            cluster_reviews = [reviews[i] for i in idxs]
            cluster_embs = embeddings[idxs]

            centroid_local = self._top_k_local(cluster_embs)

            if label == -1:
                clusters.append(
                    Cluster(
                        cluster_id=-1,
                        label="Other",
                        reviews=cluster_reviews,
                        centroid_indices=centroid_local,
                    )
                )
            else:
                clusters.append(
                    Cluster(
                        cluster_id=int(label),
                        reviews=cluster_reviews,
                        centroid_indices=centroid_local,
                    )
                )

        # Sort: named clusters first (id >= 0), Other last
        clusters.sort(key=lambda c: (c.cluster_id == -1, c.cluster_id))
        return clusters

    def _top_k_local(self, cluster_embs: np.ndarray) -> List[int]:
        """Indices (within cluster) of the top-k reviews closest to centroid."""
        k = min(self.top_k, len(cluster_embs))
        centroid = cluster_embs.mean(axis=0)
        distances = np.linalg.norm(cluster_embs - centroid, axis=1)
        return np.argsort(distances)[:k].tolist()
