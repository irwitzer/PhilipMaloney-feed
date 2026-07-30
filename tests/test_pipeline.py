"""Tests für die End-to-End-Episodenaufbereitung."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from maloney_feed.models import Episode
from maloney_feed.pipeline import (
    PipelineResult,
    ResolutionFailure,
    resolve_catalog_entries,
)
from maloney_feed.srf_catalog import SrfCatalogEpisode
from maloney_feed.srf_media import SrfAudioResource

NOW = datetime(2026, 7, 28, tzinfo=UTC)


def catalog_entry(
    *,
    episode_id: str,
    published_at: datetime | None = None,
    available: bool = True,
    available_from: datetime | None = None,
    available_to: datetime | None = None,
) -> SrfCatalogEpisode:
    return SrfCatalogEpisode(
        episode=Episode(
            episode_id=episode_id,
            title=f"Titel {episode_id}",
            page_url=f"https://www.srf.ch/audio/maloney/{episode_id}",
            audio_url=None,
            published_at=published_at or NOW - timedelta(days=1),
            description="Beschreibung",
            duration_seconds=1500,
        ),
        asset_urn=f"urn:srf:audio:{episode_id}",
        available=available,
        available_from=available_from,
        available_to=available_to,
    )


def audio_resource(episode_id: str) -> SrfAudioResource:
    return SrfAudioResource(
        url=f"https://download-media.srf.ch/{episode_id}.mp3",
        mime_type="audio/mpeg",
        quality="HD",
        duration_seconds=1500,
        valid_from=NOW - timedelta(days=1),
        valid_to=NOW + timedelta(days=364),
        playable_abroad=True,
        displayable=True,
    )


class FakeMediaClient:
    def __enter__(self) -> "FakeMediaClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def fetch(self, asset_urn: str) -> SrfAudioResource | None:
        episode_id = asset_urn.rsplit(":", 1)[-1]
        if episode_id == "NO-AUDIO":
            return None
        if episode_id == "ERROR":
            raise RuntimeError("Simulierter SRF-Fehler")
        return audio_resource(episode_id)


def run(entries: list[SrfCatalogEpisode]) -> PipelineResult:
    with patch(
        "maloney_feed.pipeline.SrfMediaClient",
        FakeMediaClient,
    ):
        return resolve_catalog_entries(
            entries,
            now=NOW,
            max_workers=2,
        )


def test_resolves_available_episodes_and_sorts_newest_first() -> None:
    older = catalog_entry(
        episode_id="OLDER",
        published_at=NOW - timedelta(days=10),
    )
    newer = catalog_entry(
        episode_id="NEWER",
        published_at=NOW - timedelta(days=2),
    )

    result = run([older, newer])

    assert [episode.episode_id for episode in result.episodes] == [
        "NEWER",
        "OLDER",
    ]
    assert result.catalog_count == 2
    assert result.failures == ()


def test_skips_catalog_entry_marked_unavailable() -> None:
    result = run([
        catalog_entry(
            episode_id="UNAVAILABLE",
            available=False,
        )
    ])

    assert result.episodes == ()
    assert result.skipped_unavailable == 1


def test_skips_episode_before_availability_start() -> None:
    result = run([
        catalog_entry(
            episode_id="FUTURE",
            available_from=NOW + timedelta(hours=1),
        )
    ])

    assert result.episodes == ()
    assert result.skipped_unavailable == 1


def test_skips_episode_at_availability_end() -> None:
    result = run([
        catalog_entry(
            episode_id="ENDED",
            available_to=NOW,
        )
    ])

    assert result.episodes == ()
    assert result.skipped_unavailable == 1


def test_skips_episode_older_than_365_days() -> None:
    result = run([
        catalog_entry(
            episode_id="OLD",
            published_at=NOW - timedelta(days=366),
        )
    ])

    assert result.episodes == ()
    assert result.skipped_expired == 1


def test_counts_missing_audio_without_treating_it_as_error() -> None:
    result = run([catalog_entry(episode_id="NO-AUDIO")])

    assert result.episodes == ()
    assert result.failures == ()
    assert result.skipped_without_audio == 1


def test_collects_individual_resolution_error_and_continues() -> None:
    result = run([
        catalog_entry(episode_id="ERROR"),
        catalog_entry(episode_id="WORKS"),
    ])

    assert [episode.episode_id for episode in result.episodes] == ["WORKS"]
    assert result.failures == (
        ResolutionFailure(
            episode_id="ERROR",
            title="Titel ERROR",
            reason="Simulierter SRF-Fehler",
        ),
    )


@pytest.mark.parametrize(
    ("maximum_age_days", "max_workers"),
    [(0, 1), (365, 0)],
)
def test_rejects_invalid_limits(
    maximum_age_days: int,
    max_workers: int,
) -> None:
    with pytest.raises(ValueError):
        resolve_catalog_entries(
            [],
            now=NOW,
            maximum_age_days=maximum_age_days,
            max_workers=max_workers,
        )
