"""Tests for retry behavior in app.services.http_client."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.http_client import request_with_retry


@pytest.mark.asyncio
async def test_retries_on_timeout_then_succeeds():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.request = AsyncMock(
        side_effect=[
            httpx.TimeoutException("timeout"),
            httpx.TimeoutException("timeout"),
            httpx.Response(200),
        ]
    )

    with patch("app.services.http_client.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        response = await request_with_retry(client, "GET", "http://example.com")

    assert response.status_code == 200
    assert client.request.call_count == 3
    assert sleep_mock.await_count == 2


@pytest.mark.asyncio
async def test_retries_on_retryable_status_then_succeeds():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.request = AsyncMock(
        side_effect=[
            httpx.Response(429),
            httpx.Response(503),
            httpx.Response(200),
        ]
    )

    with patch("app.services.http_client.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        response = await request_with_retry(client, "GET", "http://example.com")

    assert response.status_code == 200
    assert client.request.call_count == 3
    assert sleep_mock.await_count == 2


@pytest.mark.asyncio
async def test_does_not_retry_non_retryable_4xx():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.request = AsyncMock(return_value=httpx.Response(400))

    with patch("app.services.http_client.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        response = await request_with_retry(client, "GET", "http://example.com")

    assert response.status_code == 400
    assert client.request.call_count == 1
    assert sleep_mock.await_count == 0


@pytest.mark.asyncio
async def test_raises_after_retry_budget_exhausted():
    client = AsyncMock(spec=httpx.AsyncClient)
    client.request = AsyncMock(side_effect=httpx.ConnectError("connection failed"))

    with patch("app.services.http_client.asyncio.sleep", new_callable=AsyncMock) as sleep_mock:
        with pytest.raises(httpx.ConnectError):
            await request_with_retry(client, "GET", "http://example.com")

    assert client.request.call_count == 3
    assert sleep_mock.await_count == 2
