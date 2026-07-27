"""Auflösung direkter SRF-Audioressourcen über den Integration Layer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import httpx

from maloney_feed.models import Episode
from maloney_feed.srf_catalog import (
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_USER_AGENT,
    SrfCatalogEpisode,
    SrfSourceError,
)

INTEGRATION_LAYER_BASE_URL = (
    "https://il.srgssr.ch/integrationlayer/2.1/"
    "mediaComposition/byUrn"
)


@dataclass(frozen=True, slots=True)
class SrfAudioResource:
    """Ausgewählte progressive Audioressource einer SRF-Episode."""

    url: str
    mime_type: str
    quality: str | None
    duration_seconds: int | None
    valid_from: datetime | None
    valid_to: datetime | None
    playable_abroad: bool
    displayable: bool


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


def build_media_url(asset_urn: str) -> str:
    """Erzeugt die vollständige Integration-Layer-URL."""
    if not asset_urn.strip():
        raise ValueError("asset_urn darf nicht leer sein.")

    encoded_urn = quote(asset_urn.strip(), safe=":")
    return (
        f"{INTEGRATION_LAYER_BASE_URL}/{encoded_urn}"
        "?onlyChapters=true&vector=portalplay"
    )


def _is_progressive_mp3(resource: Mapping[str, Any]) -> bool:
    return (
        resource.get("protocol") == "HTTPS"
        and resource.get("streaming") == "PROGRESSIVE"
        and resource.get("mimeType") == "audio/mpeg"
        and resource.get("encoding") == "MP3"
        and resource.get("live") is False
        and isinstance(resource.get("url"), str)
        and bool(resource["url"].strip())
    )


def _resource_score(resource: Mapping[str, Any]) -> tuple[int, int]:
    return (
        1 if resource.get("quality") == "HD" else 0,
        1 if resource.get("presentation") == "DEFAULT" else 0,
    )


def _find_matching_chapter(
    chapter_list: Sequence[object],
    *,
    asset_urn: str,
) -> Mapping[str, Any] | None:
    valid_chapters = [
        chapter for chapter in chapter_list if isinstance(chapter, Mapping)
    ]

    for chapter in valid_chapters:
        if chapter.get("urn") == asset_urn:
            return chapter

    if len(valid_chapters) == 1:
        return valid_chapters[0]

    return None


def parse_media_composition(
    payload: object,
    *,
    asset_urn: str,
) -> SrfAudioResource | None:
    """Wählt die beste progressive HTTPS-MP3-Ressource aus."""
    if not isinstance(payload, Mapping):
        raise SrfSourceError(
            "Die SRF-Medienantwort ist kein JSON-Objekt."
        )

    chapter_list = payload.get("chapterList")
    if not isinstance(chapter_list, Sequence) or isinstance(
        chapter_list,
        (str, bytes),
    ):
        raise SrfSourceError("Die SRF-Medienantwort enthält keine chapterList.")

    chapter = _find_matching_chapter(chapter_list, asset_urn=asset_urn)
    if chapter is None:
        return None

    if chapter.get("displayable") is False:
        return None

    resource_list = chapter.get("resourceList")
    if not isinstance(resource_list, Sequence) or isinstance(
        resource_list,
        (str, bytes),
    ):
        return None

    candidates = [
        resource
        for resource in resource_list
        if isinstance(resource, Mapping) and _is_progressive_mp3(resource)
    ]
    if not candidates:
        return None

    selected = max(candidates, key=_resource_score)
    duration_ms = chapter.get("duration")
    duration_seconds = (
        round(duration_ms / 1000)
        if isinstance(duration_ms, int) and duration_ms >= 0
        else None
    )

    return SrfAudioResource(
        url=str(selected["url"]).strip(),
        mime_type=str(selected["mimeType"]),
        quality=(
            str(selected["quality"])
            if isinstance(selected.get("quality"), str)
            else None
        ),
        duration_seconds=duration_seconds,
        valid_from=_parse_datetime(chapter.get("validFrom")),
        valid_to=_parse_datetime(chapter.get("validTo")),
        playable_abroad=chapter.get("playableAbroad") is True,
        displayable=chapter.get("displayable") is not False,
    )


def attach_audio_resource(
    catalog_entry: SrfCatalogEpisode,
    resource: SrfAudioResource,
) -> Episode:
    """Erzeugt aus Katalog- und Mediendaten eine abspielbare Episode."""
    source = catalog_entry.episode
    return Episode(
        episode_id=source.episode_id,
        title=source.title,
        page_url=source.page_url,
        audio_url=resource.url,
        published_at=source.published_at,
        description=source.description,
        duration_seconds=(
            resource.duration_seconds
            if resource.duration_seconds is not None
            else source.duration_seconds
        ),
        audio_type=resource.mime_type,
    )


class SrfMediaClient:
    """HTTP-Client für die SRF-Medienauflösung."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            follow_redirects=True,
            timeout=timeout_seconds,
            headers={"User-Agent": DEFAULT_USER_AGENT},
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> SrfMediaClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch(self, asset_urn: str) -> SrfAudioResource | None:
        """Lädt und analysiert die Medienzusammensetzung einer Episode."""
        try:
            response = self._client.get(build_media_url(asset_urn))
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SrfSourceError(
                f"SRF-Medienressource konnte nicht geladen werden: {asset_urn}"
            ) from exc

        return parse_media_composition(payload, asset_urn=asset_urn)
