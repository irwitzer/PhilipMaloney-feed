"""Tests für die direkte SRF-Katalogschnittstelle."""

from datetime import UTC, datetime

import httpx
import pytest

from maloney_feed.srf_catalog import (
    CATALOG_URL,
    SrfCatalogClient,
    SrfSourceError,
    parse_catalog_item,
    parse_catalog_page,
)


def catalog_item(
    *,
    episode_id: str = "AUDI20260726_NR_0003",
    asset_urn: str = "urn:srf:audio:aec0b1b2-f05f-3d21-8ef4-0da02878fa2d",
) -> dict[str, object]:
    return {
        "identifier": episode_id,
        "id": episode_id,
        "title": "Superfood",
        "url": f"/audio/maloney/superfood?id={episode_id}",
        "publishedAt": "2026-07-26T11:10:00+02:00",
        "assetUrn": asset_urn,
        "lead": "Maloney untersucht einen Fall rund um Superfood.",
        "text": "Besetzung und Erstausstrahlung 2017",
        "durationMs": 1_566_940,
        "squareImageUrl": "https://example.test/cover.jpg",
        "availability": {
            "available": True,
            "availableFrom": "2026-07-26T11:10:00+02:00",
            "availableTo": "2027-07-26T11:10:00+02:00",
        },
    }


def test_parse_catalog_item_reads_metadata() -> None:
    entry = parse_catalog_item(catalog_item())

    assert entry.episode.episode_id == "AUDI20260726_NR_0003"
    assert entry.episode.page_url == (
        "https://www.srf.ch/audio/maloney/"
        "superfood?id=AUDI20260726_NR_0003"
    )
    assert entry.episode.published_at == datetime(
        2026,
        7,
        26,
        9,
        10,
        tzinfo=UTC,
    )
    assert entry.episode.duration_seconds == 1567
    assert entry.asset_urn.startswith("urn:srf:audio:")
    assert entry.available


def test_parse_catalog_page_requires_array() -> None:
    with pytest.raises(SrfSourceError, match="kein JSON-Array"):
        parse_catalog_page({"items": []})


def test_client_fetches_multiple_pages_and_deduplicates() -> None:
    first = catalog_item(episode_id="FIRST")
    duplicate = catalog_item(episode_id="FIRST")
    second = catalog_item(episode_id="SECOND")

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(CATALOG_URL)
        page = request.url.params["page"]
        payload = [first] if page == "1" else [duplicate, second]
        return httpx.Response(200, json=payload, request=request)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        with SrfCatalogClient(client=http_client) as client:
            entries = client.fetch_latest(page_count=2)

    assert [entry.episode.episode_id for entry in entries] == [
        "FIRST",
        "SECOND",
    ]


def test_client_stops_when_page_is_empty() -> None:
    requested_pages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = request.url.params["page"]
        requested_pages.append(page)
        payload = [catalog_item()] if page == "1" else []
        return httpx.Response(200, json=payload, request=request)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        with SrfCatalogClient(client=http_client) as client:
            entries = client.fetch_latest(page_count=5)

    assert len(entries) == 1
    assert requested_pages == ["1", "2"]


def test_client_can_limit_episode_count() -> None:
    payload = [
        catalog_item(episode_id="ONE"),
        catalog_item(episode_id="TWO"),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload, request=request)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        with SrfCatalogClient(client=http_client) as client:
            entries = client.fetch_latest(
                page_count=1,
                maximum_episodes=1,
            )

    assert [entry.episode.episode_id for entry in entries] == ["ONE"]


def test_client_wraps_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        with SrfCatalogClient(client=http_client) as client:
            with pytest.raises(SrfSourceError, match="Katalogseite 1"):
                client.fetch_page(1)
