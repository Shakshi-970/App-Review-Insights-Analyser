import os
import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List


class Embedder:
    """
    Encodes review texts into dense vectors using all-MiniLM-L6-v2.
    Output shape: (n_reviews, 384).
    """

    MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self):
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            print(f"      [Embedder] Loading model {self.MODEL_NAME} from local cache...")
            try:
                # local_files_only=True skips the HuggingFace Hub network revision-check,
                # which fails in corporate networks where the subprocess has no proxy.
                self._model = SentenceTransformer(self.MODEL_NAME, local_files_only=True)
            except Exception:
                # Model not yet cached — allow a one-time download.
                print(f"      [Embedder] Not in cache, downloading {self.MODEL_NAME}...")
                self._model = SentenceTransformer(self.MODEL_NAME)
            print(f"      [Embedder] Model ready.")
        return self._model

    def embed(self, texts: List[str]) -> np.ndarray:
        """
        Batch-encode texts. Returns float32 array of shape (len(texts), 384).
        Model is loaded lazily on first call.
        """
        if not texts:
            return np.empty((0, 384), dtype=np.float32)
        embeddings = self.model.encode(
            texts,
            batch_size=64,
            show_progress_bar=True,
            convert_to_numpy=True,
        )
        return embeddings.astype(np.float32)
