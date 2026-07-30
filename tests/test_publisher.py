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


def make_episode(
    episode_id: str = "AUDI20260726_NR_0003",
    audio_url: str = "https://download-media.srf.ch/superfood.mp3",
) -> Episode:
    return Episode(
        episode_id=episode_id,
        title="Superfood",
        page_url=f"https://www.srf.ch/audio/maloney/x?id={episode_id}",
        audio_url=audio_url,
        published_at=datetime(2026, 7, 26, 9, 10, tzinfo=UTC),
        description="Beschreibung",
        duration_seconds=1567,
        audio_type="audio/mpeg",
    )


def settings() -> FeedSettings:
    return FeedSettings(
        feed_url="https://irwitzer.github.io/PhilipMaloney-feed/feed.xml",
        site_url="https://www.srf.ch/audio/maloney",
        image_url=(
            "https://irwitzer.github.io/"
            "PhilipMaloney-feed/podcast-cover.png"
        ),
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

    assert len(items) == 2

    first_guid = items[0].findtext("guid")
    second_guid = items[1].find("guid")
    assert first_guid is not None
    assert second_guid is not None

    second_guid.text = first_guid
    duplicate_xml = ET.tostring(root, encoding="unicode")

    with pytest.raises(FeedValidationError, match="Doppelte GUID"):
        validate_feed_xml(duplicate_xml)


def test_rejects_non_https_audio_url() -> None:
    with pytest.raises(FeedValidationError, match="Audio-URL"):
        build_validated_feed(
            [make_episode(audio_url="http://example.test/audio.mp3")],
            settings=settings(),
        )


def test_settings_require_https() -> None:
    invalid = FeedSettings(
        feed_url="http://example.test/feed.xml",
        site_url="https://www.srf.ch/audio/maloney",
        image_url="https://example.test/cover.png",
    )
    with pytest.raises(FeedValidationError, match="feed_url"):
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
