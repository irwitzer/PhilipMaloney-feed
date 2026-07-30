"""Tests für lokale Bild- und externe Audioressourcenprüfung."""

from pathlib import Path

import pytest

from maloney_feed.remote_validation import (
    RemoteResourceValidationError,
    collect_audio_urls,
    collect_image_urls,
    validate_local_image_assets,
)

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" version="2.0">
  <channel>
    <itunes:image href="https://example.test/site/podcast-cover.png" />
    <item>
      <itunes:image href="https://example.test/site/podcast-cover.png" />
      <enclosure url="https://media.example.test/episode-1.mp3"
                 length="123"
                 type="audio/mpeg" />
    </item>
    <item>
      <itunes:image href="https://example.test/site/podcast-cover.png" />
      <enclosure url="https://media.example.test/episode-2.mp3"
                 length="456"
                 type="audio/mpeg" />
    </item>
  </channel>
</rss>
"""


def test_collects_unique_image_and_audio_urls() -> None:
    assert collect_image_urls(FEED) == (
        "https://example.test/site/podcast-cover.png",
    )
    assert collect_audio_urls(FEED) == (
        "https://media.example.test/episode-1.mp3",
        "https://media.example.test/episode-2.mp3",
    )


def test_validates_local_feed_image(tmp_path: Path) -> None:
    public = tmp_path / "public"
    public.mkdir()
    cover = public / "podcast-cover.png"
    cover.write_bytes(b"png")

    checked = validate_local_image_assets(
        FEED,
        public_dir=public,
        public_base_url="https://example.test/site/",
    )

    assert checked == (cover,)


def test_rejects_missing_local_feed_image(tmp_path: Path) -> None:
    public = tmp_path / "public"
    public.mkdir()

    with pytest.raises(RemoteResourceValidationError, match="fehlt"):
        validate_local_image_assets(
            FEED,
            public_dir=public,
            public_base_url="https://example.test/site/",
        )


def test_rejects_external_feed_image(tmp_path: Path) -> None:
    public = tmp_path / "public"
    public.mkdir()
    external_feed = FEED.replace(
        "https://example.test/site/podcast-cover.png",
        "https://images.example.net/cover.png",
    )

    with pytest.raises(RemoteResourceValidationError, match="eigenen"):
        validate_local_image_assets(
            external_feed,
            public_dir=public,
            public_base_url="https://example.test/site/",
        )
