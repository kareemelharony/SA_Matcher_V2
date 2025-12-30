"""Operations for ingesting and refreshing seed product data."""
from __future__ import annotations

from typing import Iterable, List

from .models import ProductDetails
from .paapi_client import AmazonProductAdvertisingClient
from .parsers import parse_items_response
from .repository import DataRepository
from .utils import chunked


class SeedManager:
    def __init__(self, client: AmazonProductAdvertisingClient, repository: DataRepository) -> None:
        self.client = client
        self.repository = repository

    def ingest(self, asins: Iterable[str], force_refresh: bool = False) -> List[ProductDetails]:
        asins = list(dict.fromkeys([asin.strip().upper() for asin in asins if asin.strip()]))
        new_details: List[ProductDetails] = []
        to_fetch: List[str] = []
        for asin in asins:
            existing = self.repository.get_product(asin)
            if existing and not force_refresh:
                continue
            to_fetch.append(asin)

        for batch in chunked(to_fetch, 10):
            response = self.client.get_items(batch)
            items = parse_items_response(response)
            for details in items:
                self.repository.cache_product(details)
                new_details.append(details)
        return new_details

    def get_seed_details(self, asin: str, refresh: bool = False) -> ProductDetails | None:
        asin = asin.strip().upper()
        details = self.repository.get_product(asin)
        if details and not refresh:
            return details
        fetched = self.ingest([asin], force_refresh=True)
        return fetched[0] if fetched else None
