"""Application configuration helpers."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

CONFIG_PATH = Path(os.environ.get("SA_MATCHER_CONFIG", "config/api_keys.json"))


@dataclass
class Settings:
    """Runtime configuration loaded from a JSON file or environment variables."""

    access_key: str
    secret_key: str
    partner_tag: str
    partner_type: str = "Associates"
    marketplace: str = "www.amazon.sa"
    host: str = "webservices.amazon.sa"
    region: str = "eu-west-1"

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        """Load settings from ``path`` or the default config file.

        Raises
        ------
        FileNotFoundError
            If the configuration file does not exist and the required
            environment variables are not set.
        ValueError
            If one of the required keys is missing.
        """

        config_path = path or CONFIG_PATH
        if config_path.exists():
            data = json.loads(config_path.read_text())
        else:
            data = cls._load_from_env()

        missing = {k for k in ("access_key", "secret_key", "partner_tag") if k not in data}
        if missing:
            raise ValueError(f"Missing configuration keys: {', '.join(sorted(missing))}")

        return cls(
            access_key=data["access_key"],
            secret_key=data["secret_key"],
            partner_tag=data["partner_tag"],
            partner_type=data.get("partner_type", "Associates"),
            marketplace=data.get("marketplace", "www.amazon.sa"),
            host=data.get("host", "webservices.amazon.sa"),
            region=data.get("region", "eu-west-1"),
        )

    @staticmethod
    def _load_from_env() -> Dict[str, Any]:
        env_mapping = {
            "access_key": os.environ.get("PAAPI_ACCESS_KEY"),
            "secret_key": os.environ.get("PAAPI_SECRET_KEY"),
            "partner_tag": os.environ.get("PAAPI_PARTNER_TAG"),
            "partner_type": os.environ.get("PAAPI_PARTNER_TYPE"),
            "marketplace": os.environ.get("PAAPI_MARKETPLACE"),
            "host": os.environ.get("PAAPI_HOST"),
            "region": os.environ.get("PAAPI_REGION"),
        }
        return {k: v for k, v in env_mapping.items() if v}
