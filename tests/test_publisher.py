"""Tests für Feed-Validierung und Veröffentlichung."""

from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from maloney_feed.models import Episode
from maloney_feed.pipeline import PipelineResult
from maloney_feed.publisher import (
    FeedSettings,
    FeedValidationError,
    build_validated_feed,
    publish_pipeline_result,
    validate_feed_xml,
)

EPISODE_IMAGE_URLS = tuple(
    f"https://irwitzer.github.io/PhilipMaloney-feed/"
    f"episode-images/{number:02d}_Episodenbilder.png"
    for number in range(1, 12)
)


def make_episode(
    episode_id: str = "AUDI20260726_NR_0003",
    audio_url: str = "https://download-media.srf.ch/superfood.mp3",
    audio_length: int = 22_000_000,
) -> Episode:
    return Episode(
        episode_id=episode_id,
        title="Superfood",
        page_url=f"https://www.srf.ch/audio/maloney/x?id={episode_id}",
        audio_url=audio_url,
        published_at=datetime(2026, 7, 26, 9, 10, tzinfo=UTC),
        description="Beschreibung",
        duration_seconds=1567,
        audio_length=audio_length,
        audio_type="audio/mpeg",
    )


def settings() -> FeedSettings:
    return FeedSettings(
        feed_url="https://irwitzer.github.io/PhilipMaloney-feed/feed.xml",
        site_url="https://irwitzer.github.io/PhilipMaloney-feed/",
        image_url=(
            "https://irwitzer.github.io/"
            "PhilipMaloney-feed/podcast-cover.png"
        ),
        episode_image_urls=EPISODE_IMAGE_URLS,
        title="Philip Maloney Feed",
        description=(
            "Inoffizieller Philip Maloney Feed • Hinweis zum inoffiziellen Feed\n"
            "Alle Hörspielinhalte und Audiodateien stammen von SRF. Dieser Feed "
            "verlinkt ausschließlich auf öffentlich erreichbare SRF-Ressourcen. "
            "Audiodateien werden nicht zwischengespeichert, nicht mehr öffentlich "
            "verfügbare Episoden werden umgehend aus dem Feed entfernt.\n\n"
            "Inoffizielles Fanprojekt • Keine Verbindung zu SRF • Non-commercial"
        ),
        author="Roger Graf / SRF",
    )


def result(episodes: tuple[Episode, ...]) -> PipelineResult:
    return PipelineResult(
        episodes=episodes,
        failures=(),
        catalog_count=len(episodes),
        skipped_unavailable=0,
        skipped_expired=0,
        skipped_without_audio=0,
    )


def test_build_validated_feed_creates_valid_rss() -> None:
    xml_text = build_validated_feed([make_episode()], settings=settings())
    assert validate_feed_xml(xml_text, expected_episode_count=1) == 1
    assert 'length="22000000"' in xml_text


def test_feed_contains_project_metadata() -> None:
    xml_text = build_validated_feed([make_episode()], settings=settings())

    assert "<title>Philip Maloney Feed</title>" in xml_text
    assert (
        "<link>https://irwitzer.github.io/PhilipMaloney-feed/</link>"
        in xml_text
    )
    assert "<itunes:author>Roger Graf / SRF</itunes:author>" in xml_text
    assert "Inoffizieller Philip Maloney Feed" in xml_text
    assert "Hinweis zum inoffiziellen Feed" in xml_text
    assert "Audiodateien werden nicht zwischengespeichert" in xml_text
    assert "umgehend aus dem Feed entfernt" in xml_text
    assert "Keine Verbindung zu SRF" in xml_text
    assert "Non-commercial" in xml_text


def test_feed_uses_own_rotating_episode_images() -> None:
    xml_text = build_validated_feed(
        tuple(
            make_episode(f"AUDI202607{number:02d}_NR_0001")
            for number in range(1, 13)
        ),
        settings=settings(),
    )
    root = ET.fromstring(xml_text)
    image_urls = [
        item.find(
            "{http://www.itunes.com/dtds/podcast-1.0.dtd}image"
        ).attrib["href"]
        for item in root.findall("./channel/item")
    ]

    assert image_urls[:11] == list(EPISODE_IMAGE_URLS)
    assert image_urls[11] == EPISODE_IMAGE_URLS[0]
    assert all("srf.ch" not in url.lower() for url in image_urls)


def test_rejects_duplicate_guids() -> None:
    xml_text = build_validated_feed(
        [
            make_episode("AUDI20260726_NR_0003"),
            make_episode("AUDI20260719_NR_0003"),
        ],
        settings=settings(),
    )
    root = ET.fromstring(xml_text)
    items = root.findall("./channel/item")
    first_guid = items[0].findtext("guid")
    second_guid = items[1].find("guid")
    assert first_guid is not None
    assert second_guid is not None
    second_guid.text = first_guid

    with pytest.raises(FeedValidationError, match="Doppelte GUID"):
        validate_feed_xml(ET.tostring(root, encoding="unicode"))


def test_rejects_non_https_audio_url() -> None:
    with pytest.raises(FeedValidationError, match="Audio-URL"):
        build_validated_feed(
            [make_episode(audio_url="http://example.test/audio.mp3")],
            settings=settings(),
        )


def test_rejects_missing_audio_length() -> None:
    with pytest.raises(FeedValidationError, match="Dateigröße"):
        build_validated_feed(
            [make_episode(audio_length=0)],
            settings=settings(),
        )


def test_settings_require_https() -> None:
    invalid = FeedSettings(
        feed_url="http://example.test/feed.xml",
        site_url="https://irwitzer.github.io/PhilipMaloney-feed/",
        image_url="https://example.test/cover.png",
    )
    with pytest.raises(FeedValidationError, match="feed_url"):
        build_validated_feed([make_episode()], settings=invalid)


def test_episode_image_settings_require_https() -> None:
    invalid = FeedSettings(
        feed_url="https://example.test/feed.xml",
        site_url="https://example.test/",
        image_url="https://example.test/cover.png",
        episode_image_urls=("http://example.test/episode.png",),
    )
    with pytest.raises(FeedValidationError, match="episode_image_url"):
        build_validated_feed([make_episode()], settings=invalid)


def test_publish_writes_feed(tmp_path: Path) -> None:
    output = tmp_path / "public" / "feed.xml"
    published = publish_pipeline_result(
        result((make_episode(),)),
        settings=settings(),
        output_path=output,
    )
    assert published.episode_count == 1
    assert published.byte_count > 0
    assert output.read_text(encoding="utf-8").startswith("<?xml")
