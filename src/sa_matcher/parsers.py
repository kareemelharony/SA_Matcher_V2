"""Parsers that convert raw PA-API responses into data models."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .models import ProductDetails
from .utils import now_utc


def extract_product_details(item: Dict[str, Any]) -> ProductDetails:
    asin = item.get("ASIN")
    item_info = item.get("ItemInfo") or {}
    title = _get_nested(item_info, "Title", "DisplayValue")
    features = _ensure_list(_get_nested(item_info, "Features", "DisplayValues"))
    description = _get_nested(item_info, "ContentInfo", "ShortDescription") or ""

    browse_info = item.get("BrowseNodeInfo") or {}
    browse_nodes = browse_info.get("BrowseNodes") or []
    category = browse_nodes[0]["DisplayName"] if browse_nodes else None
    subcategory = None
    if browse_nodes and browse_nodes[0].get("Children"):
        subcategory = browse_nodes[0]["Children"][0].get("DisplayName")

    product_info = item_info.get("ProductInfo") or {}
    best_seller_rank = product_info.get("BestSellerRank") or None

    customer_reviews = item.get("CustomerReviews") or {}
    review_count = customer_reviews.get("TotalReviewCount") or customer_reviews.get("Count")
    review_rating = customer_reviews.get("StarRating")
    latest_review_text = None
    if customer_reviews.get("MostRecentReview"):
        latest_review_text = customer_reviews["MostRecentReview"].get("Body")

    offers = item.get("Offers") or {}
    price = None
    currency = None
    if offers.get("Listings"):
        listing = offers["Listings"][0]
        price_info = listing.get("Price") or {}
        price = _safe_float(price_info.get("Amount"))
        currency = price_info.get("Currency")
    elif offers.get("Summaries"):
        summary = offers["Summaries"][0]
        lowest_price = summary.get("LowestPrice") or {}
        price = _safe_float(lowest_price.get("Amount"))
        currency = lowest_price.get("Currency")

    details = ProductDetails(
        asin=asin,
        title=title or "",
        description=description or "",
        bullet_points=features,
        best_seller_rank=_safe_int(best_seller_rank),
        category=category,
        subcategory=subcategory,
        review_count=_safe_int(review_count),
        review_rating=_safe_float(review_rating),
        latest_review_text=latest_review_text,
        price=price,
        currency=currency,
        raw=item,
        fetched_at=now_utc(),
    )
    return details


def parse_items_response(response: Dict[str, Any]) -> List[ProductDetails]:
    items = response.get("ItemsResult", {}).get("Items", [])
    details: List[ProductDetails] = []
    for item in items:
        asin = item.get("ASIN")
        if not asin:
            continue
        details.append(extract_product_details(item))
    return details


def extract_related_asins(item: Dict[str, Any]) -> List[str]:
    related = []
    relationships = item.get("Relationships") or {}
    related_products = relationships.get("RelatedProducts") or []
    for product in related_products:
        if product.get("Identifiers"):
            asin = product["Identifiers"].get("ASIN")
            if asin:
                related.append(asin)
    return related


def _get_nested(data: Dict[str, Any], *keys: str) -> Optional[Any]:
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
        if data is None:
            return None
    return data


def _ensure_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
