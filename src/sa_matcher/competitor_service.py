"""High-level service that discovers and evaluates competitor products."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import pandas as pd

from .models import CandidateCollection, CompetitorRecord, ProductDetails
from .paapi_client import AmazonProductAdvertisingClient
from .parsers import extract_related_asins, parse_items_response
from .repository import DataRepository
from .similarity import SimilarityEngine
from .utils import chunked, now_utc


@dataclass
class CompetitorService:
    client: AmazonProductAdvertisingClient
    repository: DataRepository
    similarity_engine: SimilarityEngine = field(default_factory=SimilarityEngine)
    candidate_page_limit: int = 5
    max_candidates: int = 70

    def collect_candidates(self, seed: ProductDetails) -> CandidateCollection:
        seen: set[str] = {seed.asin}
        related_asins: List[str] = []

        raw_item = seed.raw or {}
        related_asins.extend(extract_related_asins(raw_item))

        keywords = seed.title[:200]
        for page in range(1, self.candidate_page_limit + 1):
            response = self.client.search_items(keywords=keywords, item_page=page)
            for item in parse_items_response(response):
                if item.asin not in seen:
                    related_asins.append(item.asin)
                    seen.add(item.asin)
                if len(related_asins) >= self.max_candidates:
                    break
            if len(related_asins) >= self.max_candidates:
                break

        browse_nodes = (raw_item.get("BrowseNodeInfo") or {}).get("BrowseNodes") or []
        for node in browse_nodes:
            node_id = node.get("Id")
            if not node_id and node.get("Ancestor"):
                node_id = node["Ancestor"].get("Id")
            if not node_id:
                continue
            for page in range(1, min(self.candidate_page_limit, 3) + 1):
                response = self.client.search_items(browse_node_id=str(node_id), item_page=page)
                for item in parse_items_response(response):
                    if item.asin not in seen:
                        related_asins.append(item.asin)
                        seen.add(item.asin)
                    if len(related_asins) >= self.max_candidates:
                        break
                if len(related_asins) >= self.max_candidates:
                    break
            if len(related_asins) >= self.max_candidates:
                break

        candidates: List[ProductDetails] = []
        for batch in chunked(related_asins[: self.max_candidates], 10):
            response = self.client.get_items(batch)
            items = parse_items_response(response)
            for item in items:
                self.repository.cache_product(item)
                candidates.append(item)
        return CandidateCollection(seed_details=seed, competitors=candidates)

    def analyse(self, seed: ProductDetails, refresh_candidates: bool = False) -> List[CompetitorRecord]:
        if refresh_candidates:
            candidate_collection = self.collect_candidates(seed)
        else:
            candidate_collection = CandidateCollection(seed, [])
            for asin in self.repository.list_seed_asins():
                if asin == seed.asin:
                    continue
                product = self.repository.get_product(asin)
                if product:
                    candidate_collection.competitors.append(product)
            if not candidate_collection.competitors:
                candidate_collection = self.collect_candidates(seed)

        scores = self.similarity_engine.compute(
            candidate_collection.seed_details, candidate_collection.competitors
        )
        timestamp = now_utc()
        records: List[CompetitorRecord] = []
        for details, score in zip(candidate_collection.competitors, scores):
            record = CompetitorRecord(
                seed_asin=seed.asin,
                competitor_asin=details.asin,
                similarity_score=float(score),
                price=details.price,
                review_rating=details.review_rating,
                review_count=details.review_count,
                best_seller_rank=details.best_seller_rank,
                captured_at=timestamp,
            )
            records.append(record)
        records.sort(key=lambda r: r.similarity_score, reverse=True)
        self.repository.store_competitor_scores(records)
        self.repository.append_snapshot(records)
        return records

    def top_competitors(self, seed_asin: str, limit: int = 10) -> List[CompetitorRecord]:
        return self.repository.competitors_for_seed(seed_asin, limit)

    def export_to_csv(self, seed_asin: str, destination: Path | str) -> None:
        self.repository.export_competitors_to_csv(seed_asin, Path(destination))

    def competitor_summary(self, seed_asin: str, limit: int = 10) -> pd.DataFrame:
        records = self.top_competitors(seed_asin, limit)
        data = [
            {
                "seed_asin": record.seed_asin,
                "competitor_asin": record.competitor_asin,
                "similarity": record.similarity_score,
                "price": record.price,
                "review_rating": record.review_rating,
                "review_count": record.review_count,
                "best_seller_rank": record.best_seller_rank,
                "captured_at": record.captured_at,
            }
            for record in records
        ]
        return pd.DataFrame(data)
