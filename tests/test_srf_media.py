"""Tests für die SRF-Audioauflösung."""

from datetime import UTC, datetime

import httpx
import pytest

from maloney_feed.models import EpisodeStatus
from maloney_feed.srf_catalog import parse_catalog_item
from maloney_feed.srf_media import (
    SrfMediaClient,
    SrfSourceError,
    attach_audio_resource,
    build_media_url,
    parse_media_composition,
)

ASSET_URN = "urn:srf:audio:aec0b1b2-f05f-3d21-8ef4-0da02878fa2d"
AUDIO_URL = "https://download-media.srf.ch/superfood.mp3"


def media_payload() -> dict[str, object]:
    return {
        "chapterList": [
            {
                "urn": ASSET_URN,
                "duration": 1_566_940,
                "validFrom": "2026-07-26T11:10:00+02:00",
                "validTo": "2027-07-26T11:10:00+02:00",
                "playableAbroad": True,
                "displayable": True,
                "resourceList": [
                    {
                        "url": AUDIO_URL,
                        "quality": "HD",
                        "protocol": "HTTPS",
                        "encoding": "MP3",
                        "mimeType": "audio/mpeg",
                        "presentation": "DEFAULT",
                        "streaming": "PROGRESSIVE",
                        "live": False,
                    }
                ],
            }
        ]
    }


def catalog_item() -> dict[str, object]:
    return {
        "identifier": "AUDI20260726_NR_0003",
        "title": "Superfood",
        "url": "/audio/maloney/superfood?id=AUDI20260726_NR_0003",
        "publishedAt": "2026-07-26T11:10:00+02:00",
        "assetUrn": ASSET_URN,
        "lead": "Beschreibung",
        "durationMs": 1_566_940,
        "availability": {"available": True},
    }


def test_build_media_url_contains_required_parameters() -> None:
    url = build_media_url(ASSET_URN)
    assert ASSET_URN in url
    assert "onlyChapters=true" in url
    assert "vector=portalplay" in url


def test_parse_media_composition_reads_resource() -> None:
    resource = parse_media_composition(media_payload(), asset_urn=ASSET_URN)

    assert resource is not None
    assert resource.url == AUDIO_URL
    assert resource.duration_seconds == 1567
    assert resource.audio_length is None
    assert resource.valid_from == datetime(
        2026,
        7,
        26,
        9,
        10,
        tzinfo=UTC,
    )


def test_media_client_reads_content_length_via_head() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and "mediaComposition" in str(request.url):
            return httpx.Response(200, json=media_payload(), request=request)
        if request.method == "HEAD" and str(request.url) == AUDIO_URL:
            return httpx.Response(
                200,
                headers={"Content-Length": "22000000"},
                request=request,
            )
        raise AssertionError(f"Unerwarteter Request: {request.method} {request.url}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        with SrfMediaClient(client=http_client) as client:
            resource = client.fetch(ASSET_URN)

    assert resource is not None
    assert resource.audio_length == 22_000_000


def test_media_client_falls_back_to_range_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and "mediaComposition" in str(request.url):
            return httpx.Response(200, json=media_payload(), request=request)
        if request.method == "HEAD":
            return httpx.Response(405, request=request)
        if request.method == "GET" and str(request.url) == AUDIO_URL:
            assert request.headers["Range"] == "bytes=0-0"
            return httpx.Response(
                206,
                headers={"Content-Range": "bytes 0-0/22000000"},
                content=b"x",
                request=request,
            )
        raise AssertionError(f"Unerwarteter Request: {request.method} {request.url}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        with SrfMediaClient(client=http_client) as client:
            resource = client.fetch(ASSET_URN)

    assert resource is not None
    assert resource.audio_length == 22_000_000


def test_attach_audio_resource_copies_length() -> None:
    entry = parse_catalog_item(catalog_item())
    parsed = parse_media_composition(media_payload(), asset_urn=ASSET_URN)
    assert parsed is not None

    from dataclasses import replace

    episode = attach_audio_resource(
        entry,
        replace(parsed, audio_length=22_000_000),
    )

    assert episode.audio_length == 22_000_000
    assert episode.status is EpisodeStatus.AVAILABLE


def test_media_client_rejects_missing_length() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and "mediaComposition" in str(request.url):
            return httpx.Response(200, json=media_payload(), request=request)
        if request.method == "HEAD":
            return httpx.Response(200, request=request)
        return httpx.Response(206, content=b"x", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        with SrfMediaClient(client=http_client) as client:
            with pytest.raises(SrfSourceError, match="Dateigröße"):
                client.fetch(ASSET_URN)
