"""Tests for app.main middleware and operational endpoints."""

import uuid

import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_request_id_header_echoes_inbound_value():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/health", headers={"X-Request-ID": "abc-123"})

    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == "abc-123"


@pytest.mark.asyncio
async def test_request_id_header_generated_when_missing():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    generated = resp.headers.get("X-Request-ID")
    assert generated is not None
    uuid.UUID(generated)


@pytest.mark.asyncio
async def test_metrics_endpoint_exposed():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        await client.get("/health")
        resp = await client.get("/metrics")

    assert resp.status_code == 200
    assert "http_requests_total" in resp.text or "http_request_duration_seconds" in resp.text
