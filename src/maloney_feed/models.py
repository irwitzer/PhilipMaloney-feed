"""Interne Datenmodelle für Maloney Feed."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class EpisodeStatus(StrEnum):
    """Interner Verarbeitungsstatus einer Episode."""

    PREVIEW = "preview"
    AVAILABLE = "available"
    INVALID = "invalid"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class Episode:
    """Normalisierte Daten einer SRF-Episode."""

    episode_id: str
    title: str
    page_url: str
    audio_url: str | None
    published_at: datetime
    description: str = ""
    duration_seconds: int | None = None
    audio_length: int | None = None
    audio_type: str | None = None

    @property
    def guid(self) -> str:
        """Liefert eine dauerhaft stabile RSS-GUID."""
        return f"urn:srf:audio:{self.episode_id}"

    @property
    def status(self) -> EpisodeStatus:
        """Ermittelt den aktuellen Episodenstatus."""
        if not self.episode_id.strip() or not self.title.strip() or not self.page_url.strip():
            return EpisodeStatus.INVALID

        if not self.audio_url:
            return EpisodeStatus.PREVIEW

        return EpisodeStatus.AVAILABLE

    def is_expired(
        self,
        *,
        now: datetime | None = None,
        maximum_age_days: int = 365,
    ) -> bool:
        """Prüft, ob die Episode die erlaubte Altersgrenze überschritten hat."""
        reference_time = now or datetime.now(UTC)

        published_at = self.published_at
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=UTC)

        return published_at < reference_time - timedelta(days=maximum_age_days)
