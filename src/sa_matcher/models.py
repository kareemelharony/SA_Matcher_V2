"""Data models for product metadata and competitor analysis."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class ProductDetails:
    asin: str
    title: str = ""
    description: str = ""
    bullet_points: List[str] = field(default_factory=list)
    best_seller_rank: Optional[int] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    review_count: Optional[int] = None
    review_rating: Optional[float] = None
    latest_review_text: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    raw: dict = field(default_factory=dict)
    fetched_at: datetime | None = None

    def merged_text(self) -> str:
        parts = [self.title or "", self.description or "", " ".join(self.bullet_points or [])]
        return "\n".join(p for p in parts if p)


@dataclass
class CompetitorRecord:
    seed_asin: str
    competitor_asin: str
    similarity_score: float
    price: Optional[float]
    review_rating: Optional[float]
    review_count: Optional[int]
    best_seller_rank: Optional[int]
    captured_at: datetime


@dataclass
class CompetitorSnapshot:
    seed_asin: str
    captured_at: datetime
    competitor_asin: str
    price: Optional[float]
    review_rating: Optional[float]
    review_count: Optional[int]
    best_seller_rank: Optional[int]


@dataclass
class CandidateCollection:
    seed_details: ProductDetails
    competitors: List[ProductDetails]
