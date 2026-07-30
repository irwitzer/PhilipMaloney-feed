"""Tests für die RSS-Feed-Erzeugung."""

from datetime import UTC, datetime, timedelta
from xml.etree import ElementTree as ET

from maloney_feed.feed import ATOM_NAMESPACE, ITUNES_NAMESPACE, build_feed
from maloney_feed.models import Episode

EPISODE_IMAGE_URLS = tuple(
    f"https://irwitzer.github.io/PhilipMaloney-feed/"
    f"episode-images/{number:02d}_Episodenbilder.png"
    for number in range(1, 12)
)


def make_episode(
    *,
    episode_id: str,
    title: str,
    published_at: datetime,
    audio_url: str | None = None,
    description: str = "",
) -> Episode:
    return Episode(
        episode_id=episode_id,
        title=title,
        page_url=f"https://www.srf.ch/audio/maloney/{episode_id}",
        audio_url=audio_url or f"https://download-media.srf.ch/{episode_id}.mp3",
        published_at=published_at,
        description=description,
        duration_seconds=1400,
        audio_length=22_000_000,
        audio_type="audio/mpeg",
    )


def build_sample_feed(episodes: list[Episode], *, now: datetime) -> str:
    return build_feed(
        episodes,
        feed_url="https://irwitzer.github.io/PhilipMaloney-feed/feed.xml",
        site_url="https://www.srf.ch/audio/maloney",
        image_url=(
            "https://irwitzer.github.io/"
            "PhilipMaloney-feed/podcast-cover.png"
        ),
        episode_image_urls=EPISODE_IMAGE_URLS,
        now=now,
    )


def test_feed_is_valid_xml() -> None:
    now = datetime(2026, 7, 27, tzinfo=UTC)
    xml = build_sample_feed([], now=now)

    root = ET.fromstring(xml)

    assert root.tag == "rss"
    assert root.attrib["version"] == "2.0"


def test_channel_contains_required_podcast_metadata() -> None:
    now = datetime(2026, 7, 27, tzinfo=UTC)
    root = ET.fromstring(build_sample_feed([], now=now))
    channel = root.find("channel")

    assert channel is not None
    assert channel.findtext("title") == "Philip Maloney – inoffizieller RSS-Feed"
    assert channel.findtext("language") == "de-ch"
    assert channel.find(f"{{{ITUNES_NAMESPACE}}}image") is not None

    atom_link = channel.find(f"{{{ATOM_NAMESPACE}}}link")
    assert atom_link is not None
    assert atom_link.attrib["rel"] == "self"
    assert atom_link.attrib["type"] == "application/rss+xml"


def test_available_episode_is_written_with_enclosure() -> None:
    now = datetime(2026, 7, 27, tzinfo=UTC)
    episode = make_episode(
        episode_id="AUDI20260726_NR_0001",
        title="Eine neue Folge",
        published_at=now - timedelta(days=1),
        description="Beschreibung",
    )

    root = ET.fromstring(build_sample_feed([episode], now=now))
    item = root.find("./channel/item")

    assert item is not None
    assert item.findtext("title") == "Eine neue Folge"
    assert item.findtext("guid") == "urn:srf:audio:AUDI20260726_NR_0001"
    assert item.findtext("description") == "Beschreibung"

    enclosure = item.find("enclosure")
    assert enclosure is not None
    assert enclosure.attrib["url"].endswith("AUDI20260726_NR_0001.mp3")
    assert enclosure.attrib["length"] == "22000000"
    assert enclosure.attrib["type"] == "audio/mpeg"


def test_preview_without_audio_is_not_written() -> None:
    now = datetime(2026, 7, 27, tzinfo=UTC)
    preview = make_episode(
        episode_id="AUDI20260802_NR_0001",
        title="Kommende Folge",
        published_at=now + timedelta(days=6),
        audio_url=None,
    )
    preview = Episode(
        episode_id=preview.episode_id,
        title=preview.title,
        page_url=preview.page_url,
        audio_url=None,
        published_at=preview.published_at,
    )

    root = ET.fromstring(build_sample_feed([preview], now=now))

    assert root.findall("./channel/item") == []


def test_expired_episode_is_not_written() -> None:
    now = datetime(2026, 7, 27, tzinfo=UTC)
    expired = make_episode(
        episode_id="AUDI20250726_NR_0001",
        title="Zu alte Folge",
        published_at=now - timedelta(days=366),
    )

    root = ET.fromstring(build_sample_feed([expired], now=now))

    assert root.findall("./channel/item") == []


def test_episodes_are_sorted_newest_first() -> None:
    now = datetime(2026, 7, 27, tzinfo=UTC)
    older = make_episode(
        episode_id="OLDER",
        title="Älter",
        published_at=now - timedelta(days=14),
    )
    newer = make_episode(
        episode_id="NEWER",
        title="Neuer",
        published_at=now - timedelta(days=7),
    )

    root = ET.fromstring(build_sample_feed([older, newer], now=now))
    titles = [item.findtext("title") for item in root.findall("./channel/item")]

    assert titles == ["Neuer", "Älter"]


def test_duplicate_episode_id_is_written_only_once() -> None:
    now = datetime(2026, 7, 27, tzinfo=UTC)
    first = make_episode(
        episode_id="SAME-ID",
        title="Erste Variante",
        published_at=now - timedelta(days=2),
    )
    second = make_episode(
        episode_id="SAME-ID",
        title="Aktuelle Variante",
        published_at=now - timedelta(days=1),
    )

    root = ET.fromstring(build_sample_feed([first, second], now=now))
    items = root.findall("./channel/item")

    assert len(items) == 1
    assert items[0].findtext("title") == "Aktuelle Variante"


def test_episode_images_rotate_in_feed_order() -> None:
    now = datetime(2026, 7, 27, tzinfo=UTC)
    episodes = [
        make_episode(
            episode_id=f"EPISODE-{number:02d}",
            title=f"Folge {number}",
            published_at=now - timedelta(days=number),
        )
        for number in range(13)
    ]

    root = ET.fromstring(build_sample_feed(episodes, now=now))
    items = root.findall("./channel/item")
    image_urls = [
        item.find(f"{{{ITUNES_NAMESPACE}}}image").attrib["href"]
        for item in items
    ]

    assert image_urls[:11] == list(EPISODE_IMAGE_URLS)
    assert image_urls[11:] == list(EPISODE_IMAGE_URLS[:2])


def test_feed_contains_no_srf_image_urls() -> None:
    now = datetime(2026, 7, 27, tzinfo=UTC)
    episode = make_episode(
        episode_id="NO-SRF-IMAGE",
        title="Eigene Illustration",
        published_at=now - timedelta(days=1),
    )

    root = ET.fromstring(build_sample_feed([episode], now=now))
    image_elements = root.findall(f".//{{{ITUNES_NAMESPACE}}}image")
    image_urls = [element.attrib["href"] for element in image_elements]

    assert image_urls
    assert all(
        url.startswith("https://irwitzer.github.io/PhilipMaloney-feed/")
        for url in image_urls
    )
    assert all("srf.ch" not in url.lower() for url in image_urls)
