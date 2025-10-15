"""Shared utility helpers for SA Matcher."""
from __future__ import annotations

import contextlib
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence, Tuple, TypeVar

T = TypeVar("T")


def chunked(iterable: Sequence[T] | Iterable[T], size: int) -> Iterator[List[T]]:
    """Yield lists with ``size`` elements from ``iterable``."""

    if size <= 0:
        raise ValueError("size must be positive")

    if isinstance(iterable, Sequence):
        for start in range(0, len(iterable), size):
            yield list(iterable[start : start + size])
        return

    bucket: List[T] = []
    for item in iterable:
        bucket.append(item)
        if len(bucket) == size:
            yield bucket
            bucket = []
    if bucket:
        yield bucket


def ensure_directory(path: Path) -> None:
    """Create parent directories for ``path`` if they do not exist."""

    path.parent.mkdir(parents=True, exist_ok=True)


def now_utc() -> datetime:
    """Return the current UTC datetime without timezone info."""

    return datetime.utcnow()


def dumps_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with contextlib.suppress(json.JSONDecodeError):
        return json.loads(path.read_text())
    return {}
