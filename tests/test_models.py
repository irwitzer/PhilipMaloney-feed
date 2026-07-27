"""Tests für das Episodenmodell."""

from datetime import UTC, datetime, timedelta

from maloney_feed.models import Episode, EpisodeStatus


def make_episode(
    *,
    episode_id: str = "AUDI20260628_NR_0003",
    title: str = "Das Erlebnishotel",
    page_url: str = (
        "https://www.srf.ch/audio/maloney/"
        "das-erlebnishotel?id=AUDI20260628_NR_0003"
    ),
    audio_url: str | None = "https://download-media.srf.ch/episode.mp3",
    published_at: datetime | None = None,
) -> Episode:
    return Episode(
        episode_id=episode_id,
        title=title,
        page_url=page_url,
        audio_url=audio_url,
        published_at=published_at or datetime(2026, 6, 28, 9, 10, tzinfo=UTC),
    )


def test_guid_is_based_only_on_srf_episode_id() -> None:
    episode = make_episode()
    assert episode.guid == "urn:srf:audio:AUDI20260628_NR_0003"


def test_available_episode_has_available_status() -> None:
    episode = make_episode()
    assert episode.status is EpisodeStatus.AVAILABLE


def test_episode_without_audio_is_preview() -> None:
    episode = make_episode(audio_url=None)
    assert episode.status is EpisodeStatus.PREVIEW


def test_episode_without_required_metadata_is_invalid() -> None:
    episode = make_episode(title="")
    assert episode.status is EpisodeStatus.INVALID


def test_episode_older_than_365_days_is_expired() -> None:
    now = datetime(2026, 7, 27, tzinfo=UTC)
    episode = make_episode(published_at=now - timedelta(days=366))
    assert episode.is_expired(now=now)


def test_episode_exactly_365_days_old_is_not_expired() -> None:
    now = datetime(2026, 7, 27, tzinfo=UTC)
    episode = make_episode(published_at=now - timedelta(days=365))
    assert not episode.is_expired(now=now)


def test_changed_audio_url_does_not_change_guid() -> None:
    first = make_episode(audio_url="https://example.org/first.mp3")
    second = make_episode(audio_url="https://example.org/second.mp3")
    assert first.guid == second.guid
