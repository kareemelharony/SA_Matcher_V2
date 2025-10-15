"""Utilities for computing similarity between product listings."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .models import ProductDetails


@dataclass
class SimilarityEngine:
    """Compute textual similarity between a seed listing and competitors."""

    vectorizer: TfidfVectorizer | None = None

    def __post_init__(self) -> None:
        if self.vectorizer is None:
            self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))

    def compute(self, seed: ProductDetails, competitors: Sequence[ProductDetails]) -> List[float]:
        """Return similarity scores for ``competitors`` relative to ``seed``."""

        documents = [seed.merged_text()] + [item.merged_text() for item in competitors]
        matrix = self.vectorizer.fit_transform(documents)
        similarity_matrix = cosine_similarity(matrix[0:1], matrix[1:])
        return similarity_matrix.flatten().tolist()
