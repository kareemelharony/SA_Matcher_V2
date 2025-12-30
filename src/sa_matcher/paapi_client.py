"""Minimal Amazon Product Advertising API 5.0 client."""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import requests

from .config import Settings

ISO8601 = "%Y%m%dT%H%M%SZ"
DATE_STAMP = "%Y%m%d"
SERVICE = "ProductAdvertisingAPI"


@dataclass
class AmazonProductAdvertisingClient:
    """Simple wrapper around the signed PA-API HTTP requests."""

    settings: Settings
    timeout: int = 20

    def _sign(self, payload: str, target: str, timestamp: dt.datetime) -> Dict[str, str]:
        date_stamp = timestamp.strftime(DATE_STAMP)
        canonical_uri = "/paapi5/{target}".format(target=target)
        canonical_querystring = ""
        canonical_headers = (
            f"content-encoding:amz-1.0\n"
            f"content-type:application/json; charset=utf-8\n"
            f"host:{self.settings.host}\n"
            f"x-amz-date:{timestamp.strftime(ISO8601)}\n"
            f"x-amz-target:com.amazon.paapi5.v1.ProductAdvertisingAPIv1.{target}\n"
        )
        signed_headers = "content-encoding;content-type;host;x-amz-date;x-amz-target"
        payload_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        canonical_request = (
            f"POST\n{canonical_uri}\n{canonical_querystring}\n"
            f"{canonical_headers}\n{signed_headers}\n{payload_hash}"
        )

        algorithm = "AWS4-HMAC-SHA256"
        credential_scope = f"{date_stamp}/{self.settings.region}/{SERVICE}/aws4_request"
        string_to_sign = (
            f"{algorithm}\n{timestamp.strftime(ISO8601)}\n{credential_scope}\n"
            f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
        )

        signing_key = self._get_signature_key(
            self.settings.secret_key, date_stamp, self.settings.region, SERVICE
        )
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        authorization_header = (
            f"{algorithm} Credential={self.settings.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        return {
            "Content-Encoding": "amz-1.0",
            "Content-Type": "application/json; charset=utf-8",
            "Host": self.settings.host,
            "X-Amz-Date": timestamp.strftime(ISO8601),
            "X-Amz-Target": f"com.amazon.paapi5.v1.ProductAdvertisingAPIv1.{target}",
            "Authorization": authorization_header,
        }

    @staticmethod
    def _get_signature_key(key: str, date_stamp: str, region_name: str, service_name: str) -> bytes:
        def sign(key_bytes: bytes, msg: str) -> bytes:
            return hmac.new(key_bytes, msg.encode("utf-8"), hashlib.sha256).digest()

        k_date = sign(("AWS4" + key).encode("utf-8"), date_stamp)
        k_region = sign(k_date, region_name)
        k_service = sign(k_region, service_name)
        k_signing = sign(k_service, "aws4_request")
        return k_signing

    def _request(self, target: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        payload_str = json.dumps(payload, separators=(",", ":"))
        timestamp = dt.datetime.utcnow()
        headers = self._sign(payload_str, target, timestamp)
        endpoint = f"https://{self.settings.host}/paapi5/{target}"
        response = requests.post(endpoint, data=payload_str, headers=headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def get_items(self, asins: Iterable[str], resources: Optional[List[str]] = None) -> Dict[str, Any]:
        resources = resources or DEFAULT_RESOURCES
        payload = {
            "ItemIds": list(asins),
            "Resources": resources,
            "PartnerTag": self.settings.partner_tag,
            "PartnerType": self.settings.partner_type,
            "Marketplace": self.settings.marketplace,
        }
        return self._request("getitems", payload)

    def search_items(
        self,
        keywords: Optional[str] = None,
        browse_node_id: Optional[str] = None,
        search_index: Optional[str] = None,
        item_page: int = 1,
        resources: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "Keywords": keywords,
            "ItemPage": item_page,
            "PartnerTag": self.settings.partner_tag,
            "PartnerType": self.settings.partner_type,
            "Marketplace": self.settings.marketplace,
        }
        if browse_node_id:
            payload["BrowseNodeId"] = browse_node_id
        if search_index:
            payload["SearchIndex"] = search_index
        payload = {k: v for k, v in payload.items() if v is not None}
        payload["Resources"] = resources or DEFAULT_RESOURCES
        return self._request("searchitems", payload)

    def get_variations(self, asin: str, resources: Optional[List[str]] = None) -> Dict[str, Any]:
        payload = {
            "ASIN": asin,
            "PartnerTag": self.settings.partner_tag,
            "PartnerType": self.settings.partner_type,
            "Marketplace": self.settings.marketplace,
            "Resources": resources or DEFAULT_RESOURCES,
        }
        return self._request("getvariations", payload)


DEFAULT_RESOURCES = [
    "ItemInfo.Title",
    "ItemInfo.Features",
    "ItemInfo.ProductInfo",
    "ItemInfo.Classifications",
    "ItemInfo.ContentInfo",
    "BrowseNodeInfo.BrowseNodes",
    "Offers.Listings.Price",
    "Offers.Summaries.LowestPrice",
    "Offers.Summaries.HighestPrice",
    "Offers.Listings.MerchantInfo",
    "Offers.Listings.Condition",
    "Offers.Listings.DeliveryInfo.IsPrimeEligible",
    "CustomerReviews.Count",
    "CustomerReviews.StarRating",
    "CustomerReviews.TotalReviewCount",
    "CustomerReviews.MostRecentReview",
    "Images.Primary.Medium",
    "Images.Variants.Medium",
    "Relationships.RelatedProducts",
]
