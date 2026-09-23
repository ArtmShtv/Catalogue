from __future__ import annotations

import json
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from services.catalog_client import (
    CatalogClientError,
    CatalogNotFoundError,
    CatalogUnavailableError,
)
from services.quote_store import get_store


def _json_error(message: str, status: int) -> JsonResponse:
    return JsonResponse(
        {"error": message},
        status=status,
    )


def _parse_json_body(request: HttpRequest) -> dict[str, Any] | None:
    try:
        payload = json.loads(request.body)
    except (TypeError, ValueError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    return payload


def _validate_quote_payload(
    payload: dict[str, Any],
) -> str | None:
    author = payload.get("author")
    text = payload.get("text")

    if not isinstance(author, str):
        return "author must be a string"

    if not 1 <= len(author) <= 200:
        return "author must contain between 1 and 200 characters"

    if not isinstance(text, str):
        return "text must be a string"

    if not 1 <= len(text) <= 16384:
        return "text must contain between 1 and 16384 characters"

    return None


@csrf_exempt
@require_http_methods(["GET"])
def health(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"}, status=200)


@csrf_exempt
@require_http_methods(["POST"])
def set_catalog_source(request: HttpRequest) -> JsonResponse:
    payload = _parse_json_body(request)

    if payload is None:
        return _json_error("request body must be a JSON object", 400)

    source = payload.get("url")

    if not isinstance(source, str) or not source.strip():
        return _json_error("url must be a non-empty string", 400)

    source = source.strip().rstrip("/")

    if not source.startswith(("http://", "https://")):
        return _json_error(
            "url must start with http:// or https://",
            400,
        )

    store = get_store()
    store.set_catalog_source(source)

    return JsonResponse(
        {"source": source},
        status=200,
    )


@csrf_exempt
@require_http_methods(["POST"])
def import_snapshot(request: HttpRequest) -> JsonResponse:
    content_type = request.content_type or ""

    if "application/json" not in content_type:
        return _json_error(
            "Content-Type must be application/json",
            400,
        )

    store = get_store()

    try:
        result = store.import_snapshot(
            request.META["wsgi.input"],
        )
    except (ValueError, TypeError) as exc:
        return _json_error(str(exc), 400)

    return JsonResponse(
        {
            "imported": int(result["imported"]),
            "dropped": int(result["dropped"]),
        },
        status=200,
    )


@csrf_exempt
@require_http_methods(["GET"])
def get_quote(
    request: HttpRequest,
    quote_id: str,
) -> JsonResponse:
    store = get_store()

    local_quote = store.get(quote_id)

    if local_quote is not None:
        store.stats_increment("served_local")

        return JsonResponse(
            local_quote,
            status=200,
            headers={
                "X-Source": "LOCAL",
            },
        )

    client = store.catalog_client()

    if client is None:
        return _json_error("quote not found", 404)

    try:
        catalog_quote = client.get_quote(quote_id)
    except CatalogNotFoundError:
        # Negative results must not be cached.
        return _json_error("quote not found", 404)
    except CatalogUnavailableError:
        return _json_error(
            "catalog is temporarily unavailable",
            503,
        )
    except CatalogClientError:
        return _json_error(
            "catalog request failed",
            502,
        )

    if catalog_quote is None:
        return _json_error("quote not found", 404)

    store.stats_increment("served_from_catalog")

    # Cache the successful response locally.
    store.put(quote_id, catalog_quote)

    return JsonResponse(
        catalog_quote,
        status=200,
        headers={
            "X-Source": "CATALOG",
        },
    )


@csrf_exempt
@require_http_methods(["PUT"])
def update_quote(
    request: HttpRequest,
    quote_id: str,
) -> JsonResponse:
    payload = _parse_json_body(request)

    if payload is None:
        return _json_error("request body must be a JSON object", 400)

    validation_error = _validate_quote_payload(payload)

    if validation_error is not None:
        return _json_error(validation_error, 400)

    store = get_store()
    client = store.catalog_client()

    if client is None:
        return _json_error(
            "catalog source has not been configured",
            503,
        )

    try:
        updated_quote = client.update_quote(
            quote_id=quote_id,
            author=payload["author"],
            text=payload["text"],
        )
    except CatalogNotFoundError:
        return _json_error("quote not found", 404)
    except CatalogUnavailableError:
        return _json_error(
            "catalog is temporarily unavailable",
            503,
        )
    except CatalogClientError:
        return _json_error(
            "catalog request failed",
            502,
        )

    if not isinstance(updated_quote, dict):
        return _json_error(
            "catalog returned an invalid quote",
            502,
        )

    store.put(quote_id, updated_quote)

    return JsonResponse(
        updated_quote,
        status=200,
    )


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_quote(
    request: HttpRequest,
    quote_id: str,
) -> JsonResponse:
    store = get_store()
    client = store.catalog_client()

    if client is None:
        return _json_error(
            "catalog source has not been configured",
            503,
        )

    try:
        client.delete_quote(quote_id)
    except CatalogNotFoundError:
        return _json_error("quote not found", 404)
    except CatalogUnavailableError:
        return _json_error(
            "catalog is temporarily unavailable",
            503,
        )
    except CatalogClientError:
        return _json_error(
            "catalog request failed",
            502,
        )

    store.delete(quote_id)

    return JsonResponse(
        {"deleted": True},
        status=200,
    )


@csrf_exempt
@require_http_methods(["GET"])
def stats(request: HttpRequest) -> JsonResponse:
    store = get_store()

    return JsonResponse(
        store.get_stats(),
        status=200,
    )