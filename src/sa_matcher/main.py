"""Command line interface for SA Matcher."""
from __future__ import annotations

import argparse
from pathlib import Path

from .competitor_service import CompetitorService
from .config import Settings
from .paapi_client import AmazonProductAdvertisingClient
from .repository import DataRepository
from .seed_manager import SeedManager
from .similarity import SimilarityEngine


def build_services() -> tuple[SeedManager, CompetitorService]:
    settings = Settings.load()
    client = AmazonProductAdvertisingClient(settings)
    repository = DataRepository()
    seed_manager = SeedManager(client, repository)
    competitor_service = CompetitorService(
        client=client, repository=repository, similarity_engine=SimilarityEngine()
    )
    return seed_manager, competitor_service


def cmd_ingest(args: argparse.Namespace) -> None:
    seed_manager, _ = build_services()
    details = seed_manager.ingest(args.asins, force_refresh=args.force)
    print(f"Fetched {len(details)} listings")


def cmd_competitors(args: argparse.Namespace) -> None:
    seed_manager, competitor_service = build_services()
    seed = seed_manager.get_seed_details(args.asin, refresh=args.refresh)
    if not seed:
        raise SystemExit(f"Unable to locate seed product for ASIN {args.asin}")
    records = competitor_service.analyse(seed, refresh_candidates=args.refresh_candidates)
    top_records = records[: args.limit]
    for record in top_records:
        print(
            f"ASIN {record.competitor_asin}: score={record.similarity_score:.3f}, "
            f"price={record.price}, reviews={record.review_count}, rating={record.review_rating}"
        )
    if args.export:
        competitor_service.export_to_csv(seed.asin, Path(args.export))
        print(f"Exported competitor list to {args.export}")


def cmd_dashboard(args: argparse.Namespace) -> None:
    import subprocess

    script_path = Path(__file__).resolve().parent / "dashboard.py"
    subprocess.run(["streamlit", "run", str(script_path)], check=False)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyse Amazon.sa listings and competitors")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Fetch seed listing details for ASINs")
    ingest_parser.add_argument("asins", nargs="+", help="ASINs to ingest")
    ingest_parser.add_argument("--force", action="store_true", help="Refresh even if cached")
    ingest_parser.set_defaults(func=cmd_ingest)

    competitors_parser = subparsers.add_parser(
        "competitors", help="Compute competitor similarity for a seed ASIN"
    )
    competitors_parser.add_argument("asin", help="Seed ASIN")
    competitors_parser.add_argument("--limit", type=int, default=10)
    competitors_parser.add_argument(
        "--refresh", action="store_true", help="Refresh the seed listing before analysis"
    )
    competitors_parser.add_argument(
        "--refresh-candidates",
        action="store_true",
        help="Refresh the competitor candidate pool from Amazon",
    )
    competitors_parser.add_argument("--export", help="Export results to CSV at this path")
    competitors_parser.set_defaults(func=cmd_competitors)

    dashboard_parser = subparsers.add_parser("dashboard", help="Launch the Streamlit dashboard")
    dashboard_parser.set_defaults(func=cmd_dashboard)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = create_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
