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


def media_payload(
    *,
    resources: list[dict[str, object]] | None = None,
    displayable: bool = True,
) -> dict[str, object]:
    return {
        "chapterList": [
            {
                "urn": ASSET_URN,
                "duration": 1_566_940,
                "validFrom": "2026-07-26T11:10:00+02:00",
                "validTo": "2027-07-26T11:10:00+02:00",
                "playableAbroad": True,
                "displayable": displayable,
                "resourceList": resources
                if resources is not None
                else [
                    {
                        "url": "https://download-media.srf.ch/superfood.mp3",
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


def test_parse_media_composition_selects_progressive_hd_mp3() -> None:
    payload = media_payload(
        resources=[
            {
                "url": "https://example.test/low.mp3",
                "quality": "SD",
                "protocol": "HTTPS",
                "encoding": "MP3",
                "mimeType": "audio/mpeg",
                "presentation": "DEFAULT",
                "streaming": "PROGRESSIVE",
                "live": False,
            },
            {
                "url": "https://example.test/hd.mp3",
                "quality": "HD",
                "protocol": "HTTPS",
                "encoding": "MP3",
                "mimeType": "audio/mpeg",
                "presentation": "DEFAULT",
                "streaming": "PROGRESSIVE",
                "live": False,
            },
        ]
    )

    resource = parse_media_composition(payload, asset_urn=ASSET_URN)

    assert resource is not None
    assert resource.url == "https://example.test/hd.mp3"
    assert resource.duration_seconds == 1567
    assert resource.valid_from == datetime(
        2026,
        7,
        26,
        9,
        10,
        tzinfo=UTC,
    )


def test_parse_media_composition_rejects_streaming_playlist() -> None:
    payload = media_payload(
        resources=[
            {
                "url": "https://example.test/audio.m3u8",
                "quality": "HD",
                "protocol": "HTTPS",
                "encoding": "AAC",
                "mimeType": "application/x-mpegURL",
                "presentation": "DEFAULT",
                "streaming": "HLS",
                "live": False,
            }
        ]
    )

    assert parse_media_composition(payload, asset_urn=ASSET_URN) is None


def test_parse_media_composition_rejects_hidden_chapter() -> None:
    assert (
        parse_media_composition(
            media_payload(displayable=False),
            asset_urn=ASSET_URN,
        )
        is None
    )


def test_attach_audio_resource_creates_available_episode() -> None:
    entry = parse_catalog_item(catalog_item())
    resource = parse_media_composition(
        media_payload(),
        asset_urn=ASSET_URN,
    )

    assert resource is not None
    episode = attach_audio_resource(entry, resource)

    assert episode.audio_url == (
        "https://download-media.srf.ch/superfood.mp3"
    )
    assert episode.audio_type == "audio/mpeg"
    assert episode.status is EpisodeStatus.AVAILABLE


def test_media_client_wraps_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as http_client:
        with SrfMediaClient(client=http_client) as client:
            with pytest.raises(SrfSourceError, match="Medienressource"):
                client.fetch(ASSET_URN)
