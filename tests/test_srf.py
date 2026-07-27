"""Tests für die SRF-Datenquelle."""

import json
from datetime import UTC, datetime

import httpx
import pytest

from maloney_feed.models import EpisodeStatus
from maloney_feed.srf import (
    MALONEY_URL,
    SrfClient,
    SrfSourceError,
    discover_episode_urls,
    extract_episode_id,
    parse_episode_page,
)


def episode_html(
    *,
    episode_id: str = "AUDI20260628_NR_0001",
    audio_url: str | None = "https://download-media.srf.ch/maloney.mp3",
) -> str:
    data = {
        "props": {
            "pageProps": {
                "content": {
                    "id": episode_id,
                    "title": "Das Erlebnishotel",
                    "description": "Herr Durrer verbringt einige Nächte in einem Hotel.",
                    "publishedAt": "2026-06-28T09:10:00+02:00",
                    "audioUrl": audio_url,
                    "durationSeconds": 1411,
                    "audioLength": 22_000_000,
                    "audioType": "audio/mpeg",
                }
            }
        }
    }
    return (
        '<html><head><script id="__NEXT_DATA__" type="application/json">'
        f"{json.dumps(data)}"
        "</script></head></html>"
    )


def test_extract_episode_id() -> None:
    url = (
        "https://www.srf.ch/audio/maloney/das-erlebnishotel"
        "?id=AUDI20260628_NR_0001"
    )

    assert extract_episode_id(url) == "AUDI20260628_NR_0001"


def test_discover_episode_urls_deduplicates_by_id() -> None:
    html = """
    <a href="/audio/maloney/folge-a?id=AUDI_A">A</a>
    <a href="/audio/maloney/folge-a-neu?id=AUDI_A">A erneut</a>
    <a href="https://www.srf.ch/audio/maloney/folge-b?id=AUDI_B">B</a>
    """

    assert discover_episode_urls(html) == [
        "https://www.srf.ch/audio/maloney/folge-a?id=AUDI_A",
        "https://www.srf.ch/audio/maloney/folge-b?id=AUDI_B",
    ]


def test_parse_episode_page_reads_structured_data() -> None:
    page_url = (
        "https://www.srf.ch/audio/maloney/das-erlebnishotel"
        "?id=AUDI20260628_NR_0001"
    )

    episode = parse_episode_page(episode_html(), page_url=page_url)

    assert episode.episode_id == "AUDI20260628_NR_0001"
    assert episode.title == "Das Erlebnishotel"
    assert episode.published_at == datetime(2026, 6, 28, 7, 10, tzinfo=UTC)
    assert episode.duration_seconds == 1411
    assert episode.audio_length == 22_000_000
    assert episode.audio_type == "audio/mpeg"
    assert episode.status is EpisodeStatus.AVAILABLE


def test_parse_episode_page_without_audio_creates_preview() -> None:
    page_url = (
        "https://www.srf.ch/audio/maloney/vorschau"
        "?id=AUDI20260802_NR_0001"
    )

    episode = parse_episode_page(
        episode_html(
            episode_id="AUDI20260802_NR_0001",
            audio_url=None,
        ),
        page_url=page_url,
    )

    assert episode.audio_url is None
    assert episode.status is EpisodeStatus.PREVIEW


def test_parse_episode_page_rejects_missing_structured_data() -> None:
    page_url = (
        "https://www.srf.ch/audio/maloney/leer"
        "?id=AUDI20260628_NR_0001"
    )

    with pytest.raises(SrfSourceError, match="Keine passenden"):
        parse_episode_page("<html></html>", page_url=page_url)


def test_client_discovers_and_fetches_episode() -> None:
    page_url = (
        "https://www.srf.ch/audio/maloney/das-erlebnishotel"
        "?id=AUDI20260628_NR_0001"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == MALONEY_URL:
            return httpx.Response(
                200,
                text=f'<a href="{page_url}">Folge</a>',
                request=request,
            )
        if str(request.url) == page_url:
            return httpx.Response(
                200,
                text=episode_html(),
                request=request,
            )
        return httpx.Response(404, request=request)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        with SrfClient(client=http_client) as client:
            urls = client.discover_episode_urls()
            episodes = client.fetch_episodes(urls)

    assert urls == [page_url]
    assert len(episodes) == 1
    assert episodes[0].title == "Das Erlebnishotel"


def test_client_wraps_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        with SrfClient(client=http_client) as client:
            with pytest.raises(SrfSourceError, match="SRF-Abruf fehlgeschlagen"):
                client.discover_episode_urls()
