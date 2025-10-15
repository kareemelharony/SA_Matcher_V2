"""Streamlit dashboard for visualising SA Matcher data."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from .config import Settings
from .paapi_client import AmazonProductAdvertisingClient
from .repository import DataRepository
from .seed_manager import SeedManager
from .competitor_service import CompetitorService
from .similarity import SimilarityEngine

DB_PATH = Path("data/sa_matcher.db")


@st.cache_resource
def get_services() -> tuple[SeedManager, CompetitorService, DataRepository]:
    settings = Settings.load()
    client = AmazonProductAdvertisingClient(settings)
    repository = DataRepository(DB_PATH)
    seed_manager = SeedManager(client, repository)
    competitor_service = CompetitorService(
        client=client, repository=repository, similarity_engine=SimilarityEngine()
    )
    return seed_manager, competitor_service, repository



def competitor_stats(records: pd.DataFrame) -> pd.DataFrame:
    if records.empty:
        return pd.DataFrame()

    numeric_cols = ["price", "review_rating", "review_count", "best_seller_rank"]
    numeric_records = records.copy()
    for col in numeric_cols:
        numeric_records[col] = pd.to_numeric(numeric_records[col], errors="coerce")

    def top_list(df: pd.DataFrame, column: str, ascending: bool = True) -> list[str]:
        subset = df.dropna(subset=[column])
        if subset.empty:
            return []
        ordered = subset.nsmallest(3, column) if ascending else subset.nlargest(3, column)
        return ordered["competitor_asin"].tolist()

    stats = {
        "min_price": numeric_records["price"].min(),
        "max_price": numeric_records["price"].max(),
        "min_rating": numeric_records["review_rating"].min(),
        "max_rating": numeric_records["review_rating"].max(),
        "min_reviews": numeric_records["review_count"].min(),
        "max_reviews": numeric_records["review_count"].max(),
        "strongest_price": top_list(numeric_records, "price"),
        "strongest_bsr": top_list(numeric_records, "best_seller_rank"),
        "strongest_reviews": top_list(numeric_records, "review_count", ascending=False),
        "strongest_ratings": top_list(numeric_records, "review_rating", ascending=False),
    }
    return pd.DataFrame([stats])


def main() -> None:
    st.set_page_config(page_title="SA Matcher Dashboard", layout="wide")
    st.title("Saudi Amazon Listing Competitor Monitor")

    seed_manager, competitor_service, repository = get_services()

    seeds = repository.list_seed_asins()
    selected_seed = st.sidebar.selectbox("Select Seed ASIN", options=seeds)
    refresh_seed = st.sidebar.button("Refresh Seed Data")
    refresh_competitors = st.sidebar.button("Refresh Competitors")

    if selected_seed:
        seed = seed_manager.get_seed_details(selected_seed, refresh=refresh_seed)
        if seed:
            st.subheader(f"Seed Product: {seed.title}")
            col1, col2, col3 = st.columns(3)
            col1.metric("Price", f"{seed.price or 'N/A'} {seed.currency or ''}")
            col2.metric("Reviews", seed.review_count or "N/A")
            col3.metric("Rating", seed.review_rating or "N/A")

            if refresh_competitors:
                competitor_service.analyse(seed, refresh_candidates=True)

            limit = st.sidebar.slider("Competitors to show", min_value=5, max_value=30, value=10)
            records = competitor_service.competitor_summary(seed.asin, limit)
            stats = competitor_stats(records)

            if not stats.empty:
                st.subheader("Competitor Benchmarks")
                st.table(stats)

            st.subheader("Competitors")
            if records.empty:
                st.info("No competitors found. Try refreshing the candidate pool.")
            else:
                page = st.number_input("Page", min_value=1, value=1, step=1)
                page_size = 10
                start = (page - 1) * page_size
                end = start + page_size
                page_records = records.iloc[start:end]

                for _, row in page_records.iterrows():
                    with st.container():
                        st.markdown(f"### {row['competitor_asin']} - similarity {row['similarity']:.2f}")
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("Price", row.get("price", "N/A"))
                        c2.metric("Rating", row.get("review_rating", "N/A"))
                        c3.metric("Reviews", row.get("review_count", "N/A"))
                        c4.metric("BSR", row.get("best_seller_rank", "N/A"))
                        st.markdown(f"Captured at: {row['captured_at']}")
        else:
            st.error("Seed product is not available. Try refreshing data.")
    else:
        st.info("Ingest seed ASINs using the CLI before using the dashboard.")


if __name__ == "__main__":
    main()
