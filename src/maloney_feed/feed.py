"""Erzeugung des öffentlichen RSS-Podcast-Feeds."""

from collections.abc import Iterable
from datetime import UTC, datetime
from email.utils import format_datetime
from xml.etree import ElementTree as ET

from maloney_feed.models import Episode, EpisodeStatus

ITUNES_NAMESPACE = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"

ET.register_namespace("itunes", ITUNES_NAMESPACE)
ET.register_namespace("atom", ATOM_NAMESPACE)


def _rfc2822(value: datetime) -> str:
    """Formatiert einen Zeitpunkt für RSS."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return format_datetime(value.astimezone(UTC), usegmt=True)


def _itunes_tag(name: str) -> str:
    return f"{{{ITUNES_NAMESPACE}}}{name}"


def _atom_tag(name: str) -> str:
    return f"{{{ATOM_NAMESPACE}}}{name}"


def _publishable_episodes(
    episodes: Iterable[Episode],
    *,
    now: datetime,
    maximum_age_days: int,
) -> list[Episode]:
    """Filtert, dedupliziert und sortiert veröffentlichungsfähige Episoden."""
    best_by_id: dict[str, Episode] = {}

    for episode in episodes:
        if episode.status is not EpisodeStatus.AVAILABLE:
            continue
        if episode.is_expired(now=now, maximum_age_days=maximum_age_days):
            continue
        best_by_id[episode.episode_id] = episode

    return sorted(
        best_by_id.values(),
        key=lambda episode: episode.published_at,
        reverse=True,
    )


def build_feed(
    episodes: Iterable[Episode],
    *,
    feed_url: str,
    site_url: str,
    image_url: str,
    title: str = "Philip Maloney – inoffizieller RSS-Feed",
    description: str = (
        "Inoffizieller Podcast-Feed für aktuell bei SRF verfügbare "
        "Philip-Maloney-Episoden."
    ),
    author: str = "SRF / Philip Maloney",
    language: str = "de-ch",
    category: str = "Fiction",
    now: datetime | None = None,
    maximum_age_days: int = 365,
) -> str:
    """Erzeugt einen vollständigen RSS-2.0-Podcast-Feed."""
    generated_at = now or datetime.now(UTC)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)

    publishable = _publishable_episodes(
        episodes,
        now=generated_at,
        maximum_age_days=maximum_age_days,
    )

    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = title
    ET.SubElement(channel, "link").text = site_url
    ET.SubElement(channel, "description").text = description
    ET.SubElement(channel, "language").text = language
    ET.SubElement(channel, "lastBuildDate").text = _rfc2822(generated_at)
    ET.SubElement(channel, _itunes_tag("author")).text = author
    ET.SubElement(channel, _itunes_tag("summary")).text = description
    ET.SubElement(channel, _itunes_tag("explicit")).text = "false"
    ET.SubElement(channel, _itunes_tag("category"), {"text": category})
    ET.SubElement(channel, _itunes_tag("image"), {"href": image_url})
    ET.SubElement(
        channel,
        _atom_tag("link"),
        {
            "href": feed_url,
            "rel": "self",
            "type": "application/rss+xml",
        },
    )

    image = ET.SubElement(channel, "image")
    ET.SubElement(image, "url").text = image_url
    ET.SubElement(image, "title").text = title
    ET.SubElement(image, "link").text = site_url

    for episode in publishable:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = episode.title
        ET.SubElement(item, "link").text = episode.page_url
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = episode.guid
        ET.SubElement(item, "pubDate").text = _rfc2822(episode.published_at)
        ET.SubElement(item, "description").text = episode.description
        ET.SubElement(item, _itunes_tag("explicit")).text = "false"
        ET.SubElement(item, _itunes_tag("image"), {"href": image_url})

        if episode.duration_seconds is not None:
            ET.SubElement(item, _itunes_tag("duration")).text = str(
                episode.duration_seconds
            )

        ET.SubElement(
            item,
            "enclosure",
            {
                "url": episode.audio_url or "",
                "length": str(episode.audio_length or 0),
                "type": episode.audio_type or "audio/mpeg",
            },
        )

    ET.indent(rss, space="  ")
    xml_body = ET.tostring(rss, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_body}\n'
