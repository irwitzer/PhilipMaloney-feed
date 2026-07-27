"""Direkter Zugriff auf den SRF-Maloney-Episodenkatalog."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

import httpx

from maloney_feed.models import Episode

SRF_BASE_URL = "https://www.srf.ch"
SHOW_ID = "A00361"
CATALOG_URL = (
    "https://www.srf.ch/aron/api/audio/shows/"
    f"{SHOW_ID}/latestEpisodes"
)
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_USER_AGENT = "PhilipMaloney-feed/0.1 (+GitHub)"


class SrfSourceError(RuntimeError):
    """Fehler beim Abruf oder Interpretieren einer SRF-Schnittstelle."""


@dataclass(frozen=True, slots=True)
class SrfCatalogEpisode:
    """Episodenmetadaten aus der SRF-Katalogschnittstelle."""

    episode: Episode
    asset_urn: str
    available: bool
    available_from: datetime | None = None
    available_to: datetime | None = None
    text: str = ""
    square_image_url: str | None = None


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


def _required_text(
    item: Mapping[str, Any],
    *keys: str,
) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    joined = ", ".join(keys)
    raise SrfSourceError(f"Erforderliches Textfeld fehlt: {joined}")


def _optional_text(
    item: Mapping[str, Any],
    *keys: str,
) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def parse_catalog_item(
    item: Mapping[str, Any],
    *,
    base_url: str = SRF_BASE_URL,
) -> SrfCatalogEpisode:
    """Wandelt einen SRF-Katalogeintrag in interne Modelle um."""
    episode_id = _required_text(item, "identifier", "id")
    title = _required_text(item, "title", "currentTitle")
    relative_url = _required_text(item, "url")
    asset_urn = _required_text(item, "assetUrn")
    published_at = _parse_datetime(item.get("publishedAt") or item.get("date"))

    if published_at is None:
        raise SrfSourceError(
            f"Ungültiges oder fehlendes Veröffentlichungsdatum für {episode_id}."
        )

    duration_ms = item.get("durationMs")
    duration_seconds = (
        round(duration_ms / 1000)
        if isinstance(duration_ms, int) and duration_ms >= 0
        else None
    )

    availability = item.get("availability")
    availability_mapping = (
        availability if isinstance(availability, Mapping) else {}
    )

    return SrfCatalogEpisode(
        episode=Episode(
            episode_id=episode_id,
            title=title,
            page_url=urljoin(base_url, relative_url),
            audio_url=None,
            published_at=published_at,
            description=_optional_text(item, "lead") or "",
            duration_seconds=duration_seconds,
        ),
        asset_urn=asset_urn,
        available=availability_mapping.get("available") is True,
        available_from=_parse_datetime(
            availability_mapping.get("availableFrom")
        ),
        available_to=_parse_datetime(availability_mapping.get("availableTo")),
        text=_optional_text(item, "text") or "",
        square_image_url=_optional_text(item, "squareImageUrl"),
    )


def parse_catalog_page(payload: object) -> list[SrfCatalogEpisode]:
    """Wandelt eine vollständige API-Seite in Katalogepisoden um."""
    if not isinstance(payload, list):
        raise SrfSourceError("Die SRF-Katalogantwort ist kein JSON-Array.")

    episodes: list[SrfCatalogEpisode] = []
    for raw_item in payload:
        if not isinstance(raw_item, Mapping):
            raise SrfSourceError(
                "Die SRF-Katalogantwort enthält einen ungültigen Eintrag."
            )
        episodes.append(parse_catalog_item(raw_item))

    return episodes


def deduplicate_catalog_episodes(
    episodes: Iterable[SrfCatalogEpisode],
) -> list[SrfCatalogEpisode]:
    """Entfernt doppelte Episoden und behält die zuerst gelieferte Variante."""
    unique: dict[str, SrfCatalogEpisode] = {}

    for entry in episodes:
        unique.setdefault(entry.episode.episode_id, entry)

    return list(unique.values())


class SrfCatalogClient:
    """HTTP-Client für die paginierte Maloney-Episodenliste."""

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

    def __enter__(self) -> SrfCatalogClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch_page(self, page_number: int) -> list[SrfCatalogEpisode]:
        """Lädt genau eine Katalogseite."""
        if page_number < 1:
            raise ValueError("page_number muss mindestens 1 sein.")

        try:
            response = self._client.get(
                CATALOG_URL,
                params={"page": page_number},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SrfSourceError(
                f"SRF-Katalogseite {page_number} konnte nicht geladen werden."
            ) from exc

        return parse_catalog_page(payload)

    def fetch_latest(
        self,
        *,
        page_count: int = 1,
        maximum_episodes: int | None = None,
    ) -> list[SrfCatalogEpisode]:
        """Lädt mehrere Seiten, dedupliziert und begrenzt das Ergebnis."""
        if page_count < 1:
            raise ValueError("page_count muss mindestens 1 sein.")
        if maximum_episodes is not None and maximum_episodes < 1:
            raise ValueError("maximum_episodes muss mindestens 1 sein.")

        collected: list[SrfCatalogEpisode] = []

        for page_number in range(1, page_count + 1):
            page = self.fetch_page(page_number)
            if not page:
                break
            collected.extend(page)

        unique = deduplicate_catalog_episodes(collected)
        if maximum_episodes is not None:
            return unique[:maximum_episodes]
        return unique
