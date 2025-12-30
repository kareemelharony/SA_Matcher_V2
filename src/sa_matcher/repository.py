"""SQLite repository for storing product and competitor information."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from .models import CompetitorRecord, ProductDetails
from .utils import ensure_directory, now_utc

DB_PATH = Path("data/sa_matcher.db")


class DataRepository:
    """Persistence layer handling caching and competitor snapshots."""

    def __init__(self, db_path: Path | str = DB_PATH) -> None:
        self.db_path = Path(db_path)
        ensure_directory(self.db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS seeds (
                    asin TEXT PRIMARY KEY,
                    title TEXT,
                    description TEXT,
                    bullet_points TEXT,
                    best_seller_rank INTEGER,
                    category TEXT,
                    subcategory TEXT,
                    review_count INTEGER,
                    review_rating REAL,
                    latest_review_text TEXT,
                    price REAL,
                    currency TEXT,
                    raw_json TEXT,
                    fetched_at TEXT
                );

                CREATE TABLE IF NOT EXISTS competitor_scores (
                    seed_asin TEXT NOT NULL,
                    competitor_asin TEXT NOT NULL,
                    similarity_score REAL NOT NULL,
                    price REAL,
                    review_rating REAL,
                    review_count INTEGER,
                    best_seller_rank INTEGER,
                    captured_at TEXT NOT NULL,
                    PRIMARY KEY (seed_asin, competitor_asin)
                );

                CREATE TABLE IF NOT EXISTS competitor_snapshots (
                    seed_asin TEXT NOT NULL,
                    competitor_asin TEXT NOT NULL,
                    price REAL,
                    review_rating REAL,
                    review_count INTEGER,
                    best_seller_rank INTEGER,
                    captured_at TEXT NOT NULL,
                    PRIMARY KEY (seed_asin, competitor_asin, captured_at)
                );
                """
            )

    def cache_product(self, details: ProductDetails) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO seeds (
                    asin, title, description, bullet_points, best_seller_rank,
                    category, subcategory, review_count, review_rating,
                    latest_review_text, price, currency, raw_json, fetched_at
                ) VALUES (:asin, :title, :description, :bullet_points, :best_seller_rank,
                          :category, :subcategory, :review_count, :review_rating,
                          :latest_review_text, :price, :currency, :raw_json, :fetched_at)
                ON CONFLICT(asin) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    bullet_points = excluded.bullet_points,
                    best_seller_rank = excluded.best_seller_rank,
                    category = excluded.category,
                    subcategory = excluded.subcategory,
                    review_count = excluded.review_count,
                    review_rating = excluded.review_rating,
                    latest_review_text = excluded.latest_review_text,
                    price = excluded.price,
                    currency = excluded.currency,
                    raw_json = excluded.raw_json,
                    fetched_at = excluded.fetched_at;
                """,
                {
                    "asin": details.asin,
                    "title": details.title,
                    "description": details.description,
                    "bullet_points": json.dumps(details.bullet_points, ensure_ascii=False),
                    "best_seller_rank": details.best_seller_rank,
                    "category": details.category,
                    "subcategory": details.subcategory,
                    "review_count": details.review_count,
                    "review_rating": details.review_rating,
                    "latest_review_text": details.latest_review_text,
                    "price": details.price,
                    "currency": details.currency,
                    "raw_json": json.dumps(details.raw, ensure_ascii=False),
                    "fetched_at": (details.fetched_at or now_utc()).isoformat(),
                },
            )

    def get_product(self, asin: str) -> Optional[ProductDetails]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM seeds WHERE asin = ?", (asin,)).fetchone()
        if not row:
            return None
        return ProductDetails(
            asin=row["asin"],
            title=row["title"],
            description=row["description"],
            bullet_points=json.loads(row["bullet_points"] or "[]"),
            best_seller_rank=row["best_seller_rank"],
            category=row["category"],
            subcategory=row["subcategory"],
            review_count=row["review_count"],
            review_rating=row["review_rating"],
            latest_review_text=row["latest_review_text"],
            price=row["price"],
            currency=row["currency"],
            raw=json.loads(row["raw_json"] or "{}"),
        )

    def list_seed_asins(self) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT asin FROM seeds ORDER BY asin").fetchall()
        return [row["asin"] for row in rows]

    def store_competitor_scores(self, records: Iterable[CompetitorRecord]) -> None:
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO competitor_scores (
                    seed_asin, competitor_asin, similarity_score, price,
                    review_rating, review_count, best_seller_rank, captured_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(seed_asin, competitor_asin) DO UPDATE SET
                    similarity_score = excluded.similarity_score,
                    price = excluded.price,
                    review_rating = excluded.review_rating,
                    review_count = excluded.review_count,
                    best_seller_rank = excluded.best_seller_rank,
                    captured_at = excluded.captured_at;
                """,
                [
                    (
                        record.seed_asin,
                        record.competitor_asin,
                        record.similarity_score,
                        record.price,
                        record.review_rating,
                        record.review_count,
                        record.best_seller_rank,
                        record.captured_at.isoformat(),
                    )
                    for record in records
                ],
            )

    def append_snapshot(self, records: Iterable[CompetitorRecord]) -> None:
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO competitor_snapshots (
                    seed_asin, competitor_asin, price, review_rating,
                    review_count, best_seller_rank, captured_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                [
                    (
                        record.seed_asin,
                        record.competitor_asin,
                        record.price,
                        record.review_rating,
                        record.review_count,
                        record.best_seller_rank,
                        record.captured_at.isoformat(),
                    )
                    for record in records
                ],
            )

    def competitors_for_seed(self, seed_asin: str, limit: Optional[int] = None) -> List[CompetitorRecord]:
        with self._connect() as conn:
            query = (
                "SELECT * FROM competitor_scores WHERE seed_asin = ? "
                "ORDER BY similarity_score DESC"
            )
            params = [seed_asin]
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            rows = conn.execute(query, params).fetchall()
        return [
            CompetitorRecord(
                seed_asin=row["seed_asin"],
                competitor_asin=row["competitor_asin"],
                similarity_score=row["similarity_score"],
                price=row["price"],
                review_rating=row["review_rating"],
                review_count=row["review_count"],
                best_seller_rank=row["best_seller_rank"],
                captured_at=dt_from_iso(row["captured_at"]),
            )
            for row in rows
        ]

    def export_competitors_to_csv(self, seed_asin: str, destination: Path) -> None:
        ensure_directory(destination)
        with self._connect() as conn, destination.open("w", encoding="utf-8") as fh:
            writer = fh.write
            writer("seed_asin,competitor_asin,similarity,price,review_rating,review_count,best_seller_rank,captured_at\n")
            rows = conn.execute(
                "SELECT * FROM competitor_scores WHERE seed_asin = ? ORDER BY similarity_score DESC",
                (seed_asin,),
            )
            for row in rows:
                writer(
                    ",".join(
                        [
                            seed_asin,
                            row["competitor_asin"],
                            f"{row['similarity_score']:.4f}",
                            "" if row["price"] is None else f"{row['price']}",
                            "" if row["review_rating"] is None else f"{row['review_rating']}",
                            "" if row["review_count"] is None else f"{row['review_count']}",
                            "" if row["best_seller_rank"] is None else f"{row['best_seller_rank']}",
                            row["captured_at"],
                        ]
                    )
                    + "\n"
                )


def dt_from_iso(value: str) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)
