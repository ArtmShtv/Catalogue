from __future__ import annotations

import json
import threading
from typing import Any, BinaryIO

from .catalog_client import CatalogClient


class QuoteStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._catalog_lock = threading.Lock()

        self._quotes: dict[str, bytes] = {}
        self._catalog_source: str | None = None
        self._catalog: CatalogClient | None = None

        self._stats = {
            "served_local": 0,
            "served_from_catalog": 0,
            "catalog_reads": 0,
            "evictions": 0,
        }

        self._catalog_count = 0

    def set_catalog_source(self, source: str) -> None:
        with self._lock:
            self._catalog_source = source
            self._catalog = CatalogClient(source)

    def catalog_client(self) -> CatalogClient | None:
        with self._lock:
            return self._catalog

    def get(self, quote_id: str) -> dict[str, Any] | None:
        with self._lock:
            raw = self._quotes.get(quote_id)

        if raw is None:
            return None

        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            return None

        if not isinstance(payload, dict):
            return None

        return payload

    def put(
        self,
        quote_id: str,
        quote: dict[str, Any],
    ) -> None:
        if not isinstance(quote, dict):
            raise ValueError("quote must be a JSON object")

        serialized = json.dumps(
            quote,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        with self._lock:
            self._quotes[quote_id] = serialized

    def delete(self, quote_id: str) -> bool:
        with self._lock:
            existed = quote_id in self._quotes

            if existed:
                del self._quotes[quote_id]
                self._stats["evictions"] += 1

            return existed

    def stats_increment(self, key: str) -> None:
        with self._lock:
            if key not in self._stats:
                raise KeyError(f"unknown statistic: {key}")

            self._stats[key] += 1

    def get_stats(self) -> dict[str, int]:
        with self._lock:
            local_bytes = sum(
                len(value)
                for value in self._quotes.values()
            )

            return {
                "served_local": self._stats["served_local"],
                "served_from_catalog": self._stats[
                    "served_from_catalog"
                ],
                "catalog_reads": self._stats["catalog_reads"],
                "evictions": self._stats["evictions"],
                "local": len(self._quotes),
                "bytes": local_bytes,
                "catalog": self._catalog_count,
            }

    def import_snapshot(
        self,
        stream: BinaryIO,
    ) -> dict[str, int]:
        new_quotes: dict[str, bytes] = {}
        imported = 0

        first_line = stream.readline()

        if not first_line:
            raise ValueError("empty request body")

        first_text = first_line.decode("utf-8").strip()

        if first_text != '{"quotes": [':
            raise ValueError("invalid snapshot opening line")

        for raw_line in stream:
            line = raw_line.decode("utf-8").strip()

            if not line:
                continue

            if line == "]}":
                break

            if line.endswith(","):
                line = line[:-1].rstrip()

            try:
                quote = json.loads(line)
            except (TypeError, ValueError, UnicodeDecodeError) as exc:
                raise ValueError("invalid quote JSON") from exc

            if not isinstance(quote, dict):
                raise ValueError("each quote must be an object")

            quote_id = quote.get("id")
            author = quote.get("author")
            text = quote.get("text")

            if not isinstance(quote_id, (str, int)):
                raise ValueError("quote id must be a string or integer")

            if not isinstance(author, str):
                raise ValueError("quote author must be a string")

            if not isinstance(text, str):
                raise ValueError("quote text must be a string")

            quote_id = str(quote_id)

            if not quote_id:
                raise ValueError("quote id must not be empty")

            serialized = json.dumps(
                quote,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")

            new_quotes[quote_id] = serialized
            imported += 1
        else:
            raise ValueError("snapshot closing line is missing")

        with self._lock:
            old_ids = set(self._quotes)
            new_ids = set(new_quotes)

            dropped = len(old_ids - new_ids)

            self._quotes = new_quotes
            self._catalog_count = imported

        return {
            "imported": imported,
            "dropped": dropped,
        }


_store = QuoteStore()


def get_store() -> QuoteStore:
    return _store