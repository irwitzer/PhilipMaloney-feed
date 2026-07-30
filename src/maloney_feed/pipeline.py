"""End-to-End-Aufbereitung der SRF-Episoden für den RSS-Feed."""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime

from maloney_feed.models import Episode
from maloney_feed.srf_catalog import SrfCatalogClient, SrfCatalogEpisode
from maloney_feed.srf_media import (
    SrfMediaClient,
    attach_audio_resource,
)


@dataclass(frozen=True, slots=True)
class ResolutionFailure:
    """Eine Episode, deren Audioressource nicht aufgelöst werden konnte."""

    episode_id: str
    title: str
    reason: str


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Ergebnis eines vollständigen Katalog- und Medienlaufs."""

    episodes: tuple[Episode, ...]
    failures: tuple[ResolutionFailure, ...]
    catalog_count: int
    skipped_unavailable: int
    skipped_expired: int
    skipped_without_audio: int


def _is_within_catalog_availability(
    entry: SrfCatalogEpisode,
    *,
    now: datetime,
) -> bool:
    if not entry.available:
        return False
    if entry.available_from is not None and now < entry.available_from:
        return False
    if entry.available_to is not None and now >= entry.available_to:
        return False
    return True


def _resolve_one(
    entry: SrfCatalogEpisode,
) -> tuple[Episode | None, ResolutionFailure | None]:
    try:
        with SrfMediaClient() as client:
            resource = client.fetch(entry.asset_urn)
    except Exception as exc:  # Einzelne SRF-Ausfälle sollen den Lauf nicht zerstören.
        return None, ResolutionFailure(
            episode_id=entry.episode.episode_id,
            title=entry.episode.title,
            reason=str(exc),
        )

    if resource is None:
        return None, None

    return attach_audio_resource(entry, resource), None


def resolve_catalog_entries(
    entries: Iterable[SrfCatalogEpisode],
    *,
    now: datetime | None = None,
    maximum_age_days: int = 365,
    max_workers: int = 4,
) -> PipelineResult:
    """Löst verfügbare Katalogepisoden parallel zu Feed-Episoden auf."""
    if maximum_age_days < 1:
        raise ValueError("maximum_age_days muss mindestens 1 sein.")
    if max_workers < 1:
        raise ValueError("max_workers muss mindestens 1 sein.")

    reference_time = now or datetime.now(UTC)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=UTC)

    catalog_entries = list(entries)
    candidates: list[SrfCatalogEpisode] = []
    skipped_unavailable = 0
    skipped_expired = 0

    for entry in catalog_entries:
        if not _is_within_catalog_availability(entry, now=reference_time):
            skipped_unavailable += 1
            continue
        if entry.episode.is_expired(
            now=reference_time,
            maximum_age_days=maximum_age_days,
        ):
            skipped_expired += 1
            continue
        candidates.append(entry)

    resolved: list[Episode] = []
    failures: list[ResolutionFailure] = []
    skipped_without_audio = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_resolve_one, entry): entry
            for entry in candidates
        }

        for future in as_completed(future_map):
            episode, failure = future.result()
            if failure is not None:
                failures.append(failure)
            elif episode is None:
                skipped_without_audio += 1
            else:
                resolved.append(episode)

    resolved.sort(key=lambda episode: episode.published_at, reverse=True)
    failures.sort(key=lambda failure: failure.episode_id)

    return PipelineResult(
        episodes=tuple(resolved),
        failures=tuple(failures),
        catalog_count=len(catalog_entries),
        skipped_unavailable=skipped_unavailable,
        skipped_expired=skipped_expired,
        skipped_without_audio=skipped_without_audio,
    )


def fetch_feed_episodes(
    *,
    page_count: int = 3,
    maximum_episodes: int | None = 60,
    maximum_age_days: int = 365,
    max_workers: int = 4,
    now: datetime | None = None,
) -> PipelineResult:
    """Lädt den SRF-Katalog und bereitet alle feedfähigen Episoden auf."""
    with SrfCatalogClient() as catalog_client:
        entries = catalog_client.fetch_latest(
            page_count=page_count,
            maximum_episodes=maximum_episodes,
        )

    return resolve_catalog_entries(
        entries,
        now=now,
        maximum_age_days=maximum_age_days,
        max_workers=max_workers,
    )
