"""HTTP client helpers with bounded retry behavior."""

from __future__ import annotations

import asyncio

import httpx

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
BACKOFF_SCHEDULE_SECONDS = (0.2, 0.5)


def _is_retryable_exception(exc: Exception) -> bool:
    return isinstance(
        exc,
        (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError),
    )


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs,
) -> httpx.Response:
    retries = len(BACKOFF_SCHEDULE_SECONDS)
    for attempt in range(retries + 1):
        try:
            response = await client.request(method, url, **kwargs)
        except Exception as exc:
            if not _is_retryable_exception(exc) or attempt >= retries:
                raise
            await asyncio.sleep(BACKOFF_SCHEDULE_SECONDS[attempt])
            continue

        if response.status_code in RETRYABLE_STATUS_CODES and attempt < retries:
            await asyncio.sleep(BACKOFF_SCHEDULE_SECONDS[attempt])
            continue
        return response

    raise RuntimeError("request_with_retry reached unreachable state")
