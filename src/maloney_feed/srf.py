"""Abruf und Auswertung der öffentlich verfügbaren SRF-Maloney-Seiten."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Mapping
from datetime import UTC, datetime
from html import unescape
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import httpx

from maloney_feed.models import Episode

MALONEY_URL = "https://www.srf.ch/audio/maloney"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_USER_AGENT = "PhilipMaloney-feed/0.1 (+GitHub)"

_EPISODE_LINK_PATTERN = re.compile(
    r"""href=["'](?P<url>[^"']*/audio/maloney/[^"']+\?[^"']*\bid=[^"'&]+[^"']*)["']""",
    re.IGNORECASE,
)
_SCRIPT_JSON_PATTERN = re.compile(
    r"""<script\b[^>]*type=["']application/(?:ld\+)?json["'][^>]*>(?P<body>.*?)</script>""",
    re.IGNORECASE | re.DOTALL,
)
_NEXT_DATA_PATTERN = re.compile(
    r"""<script\b[^>]*id=["']__NEXT_DATA__["'][^>]*>(?P<body>.*?)</script>""",
    re.IGNORECASE | re.DOTALL,
)


class SrfSourceError(RuntimeError):
    """Fehler beim Abruf oder Interpretieren der SRF-Quelle."""


def extract_episode_id(url: str) -> str | None:
    """Liest die stabile SRF-Episoden-ID aus der URL."""
    values = parse_qs(urlparse(url).query).get("id")
    if not values:
        return None

    episode_id = values[0].strip()
    return episode_id or None


def discover_episode_urls(html: str, *, base_url: str = MALONEY_URL) -> list[str]:
    """Extrahiert eindeutige Maloney-Episodenlinks aus einer Übersichtsseite."""
    urls_by_id: dict[str, str] = {}

    for match in _EPISODE_LINK_PATTERN.finditer(html):
        url = urljoin(base_url, unescape(match.group("url")))
        episode_id = extract_episode_id(url)
        if episode_id:
            urls_by_id.setdefault(episode_id, url)

    return list(urls_by_id.values())


def _walk_json(value: Any) -> Iterator[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _load_embedded_json(html: str) -> list[Any]:
    documents: list[Any] = []
    patterns = (_NEXT_DATA_PATTERN, _SCRIPT_JSON_PATTERN)

    for pattern in patterns:
        for match in pattern.finditer(html):
            body = unescape(match.group("body")).strip()
            if not body:
                continue
            try:
                documents.append(json.loads(body))
            except json.JSONDecodeError:
                continue

    return documents


def _first_text(mapping: Mapping[str, Any], names: Iterable[str]) -> str | None:
    for name in names:
        value = mapping.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_integer(mapping: Mapping[str, Any], names: Iterable[str]) -> int | None:
    for name in names:
        value = mapping.get(name)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _matching_episode_mapping(
    documents: Iterable[Any],
    *,
    episode_id: str,
) -> Mapping[str, Any] | None:
    candidates: list[Mapping[str, Any]] = []

    for document in documents:
        for mapping in _walk_json(document):
            candidate_id = _first_text(
                mapping,
                ("id", "urn", "episodeId", "mediaId", "contentId"),
            )
            if candidate_id and episode_id in candidate_id:
                candidates.append(mapping)

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda item: sum(
            key in item
            for key in (
                "title",
                "name",
                "description",
                "audioUrl",
                "contentUrl",
                "publishedAt",
                "datePublished",
            )
        ),
    )


def parse_episode_page(html: str, *, page_url: str) -> Episode:
    """Erzeugt aus einer SRF-Episodenseite ein Episode-Objekt."""
    episode_id = extract_episode_id(page_url)
    if not episode_id:
        raise SrfSourceError("Die Episodenseite enthält keine SRF-ID.")

    mapping = _matching_episode_mapping(
        _load_embedded_json(html),
        episode_id=episode_id,
    )
    if mapping is None:
        raise SrfSourceError(
            f"Keine passenden strukturierten Episodendaten für {episode_id} gefunden."
        )

    title = _first_text(mapping, ("title", "name", "headline"))
    published_at = _parse_datetime(
        _first_text(
            mapping,
            ("publishedAt", "datePublished", "publicationDate", "startDate"),
        )
    )
    audio_url = _first_text(
        mapping,
        ("audioUrl", "contentUrl", "downloadUrl", "mediaUrl", "url"),
    )

    if audio_url and not audio_url.lower().startswith(("http://", "https://")):
        audio_url = None

    if not title or published_at is None:
        raise SrfSourceError(
            f"Unvollständige Episodendaten für {episode_id}: Titel oder Datum fehlt."
        )

    return Episode(
        episode_id=episode_id,
        title=title,
        page_url=page_url,
        audio_url=audio_url,
        published_at=published_at,
        description=_first_text(
            mapping,
            ("description", "summary", "lead", "abstract"),
        )
        or "",
        duration_seconds=_first_integer(
            mapping,
            ("durationSeconds", "duration", "runtime"),
        ),
        audio_length=_first_integer(
            mapping,
            ("audioLength", "contentSize", "fileSize"),
        ),
        audio_type=_first_text(
            mapping,
            ("audioType", "encodingFormat", "mimeType"),
        ),
    )


class SrfClient:
    """Kleiner HTTP-Client für die SRF-Maloney-Quelle."""

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

    def __enter__(self) -> SrfClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _get_text(self, url: str) -> str:
        try:
            response = self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SrfSourceError(f"SRF-Abruf fehlgeschlagen: {url}") from exc

        return response.text

    def discover_episode_urls(self) -> list[str]:
        """Ruft die Übersicht ab und liefert die gefundenen Episodenlinks."""
        return discover_episode_urls(self._get_text(MALONEY_URL))

    def fetch_episode(self, page_url: str) -> Episode:
        """Ruft eine einzelne Episodenseite ab und wertet sie aus."""
        return parse_episode_page(self._get_text(page_url), page_url=page_url)

    def fetch_episodes(self, page_urls: Iterable[str]) -> list[Episode]:
        """Ruft mehrere Episoden ab; ein Fehler bleibt bewusst sichtbar."""
        return [self.fetch_episode(url) for url in page_urls]
