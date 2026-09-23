from __future__ import annotations

import time
from typing import Any

import requests


class CatalogClientError(Exception):
    """Base exception for catalog communication errors."""


class CatalogNotFoundError(CatalogClientError):
    """The requested quote does not exist in the catalog."""


class CatalogUnavailableError(CatalogClientError):
    """The catalog is unavailable or temporarily overloaded."""


class CatalogClient:
    def __init__(
        self,
        source: str,
        timeout: tuple[float, float] = (0.5, 1.5),
    ) -> None:
        self.source = source.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def _url(self, quote_id: str) -> str:
        return f"{self.source}/quote/{quote_id}"


    @staticmethod
    def _retry_after(response: requests.Response) -> float:
        value = response.headers.get("Retry-After")

        if value is None:
            return 0.5

        try:
            seconds = float(value)
        except (TypeError, ValueError):
            return 0.5

        return max(0.0, min(seconds, 2.0))


    def _request(
        self,
        method: str,
        quote_id: str,
        **kwargs: Any,
    ) -> requests.Response:
        try:
            response = self.session.request(
                method=method,
                url=self._url(quote_id),
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise CatalogUnavailableError(
                "catalog request failed"
            ) from exc

        if response.status_code == 404:
            raise CatalogNotFoundError("quote not found")

        if response.status_code == 503:
            retry_after = self._retry_after(response)

            # Do not sleep here. The reader must not be blocked for an
            # arbitrary amount of time by the external catalog.
            raise CatalogUnavailableError(
                f"catalog busy; retry after {retry_after:.2f}s"
            )

        if response.status_code >= 500:
            raise CatalogUnavailableError(
                f"catalog returned {response.status_code}"
            )

        if response.status_code >= 400:
            raise CatalogClientError(
                f"catalog returned {response.status_code}"
            )

        return response


    @staticmethod
    def _json_object(response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise CatalogClientError(
                "catalog returned invalid JSON"
            ) from exc

        if not isinstance(payload, dict):
            raise CatalogClientError(
                "catalog returned a JSON value instead of an object"
            )

        return payload


    def get_quote(self, quote_id: str) -> dict[str, Any]:
        response = self._request("GET", quote_id)
        return self._json_object(response)


    def update_quote(
        self,
        quote_id: str,
        author: str,
        text: str,
    ) -> dict[str, Any]:
        response = self._request(
            "PUT",
            quote_id,
            json={
                "author": author,
                "text": text,
            },
        )

        return self._json_object(response)


    def delete_quote(self, quote_id: str) -> None:
        self._request("DELETE", quote_id)