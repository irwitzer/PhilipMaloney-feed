"""Erzeugung, Validierung und atomare Speicherung des öffentlichen Feeds."""

from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from maloney_feed.feed import build_feed
from maloney_feed.models import Episode
from maloney_feed.pipeline import PipelineResult


class FeedValidationError(ValueError):
    """Der erzeugte RSS-Feed ist ungültig."""


@dataclass(frozen=True, slots=True)
class FeedSettings:
    feed_url: str
    site_url: str
    image_url: str
    title: str = "Philip Maloney – inoffizieller RSS-Feed"
    description: str = (
        "Inoffizieller Podcast-Feed für aktuell bei SRF verfügbare "
        "Philip-Maloney-Episoden."
    )
    author: str = "SRF / Philip Maloney"
    language: str = "de-ch"
    category: str = "Fiction"


@dataclass(frozen=True, slots=True)
class FeedBuildResult:
    output_path: Path
    episode_count: int
    byte_count: int


def _is_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def validate_settings(settings: FeedSettings) -> None:
    for field_name in ("feed_url", "site_url", "image_url"):
        if not _is_https_url(getattr(settings, field_name)):
            raise FeedValidationError(
                f"{field_name} muss eine vollständige HTTPS-URL sein."
            )


def validate_feed_xml(
    xml_text: str,
    *,
    expected_episode_count: int | None = None,
) -> int:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise FeedValidationError("Der Feed ist kein gültiges XML.") from exc

    if root.tag != "rss" or root.attrib.get("version") != "2.0":
        raise FeedValidationError("Der Feed ist kein RSS-2.0-Dokument.")

    channel = root.find("channel")
    if channel is None:
        raise FeedValidationError("Der Feed enthält keinen channel.")

    for tag in ("title", "link", "description", "language"):
        if not (channel.findtext(tag) or "").strip():
            raise FeedValidationError(f"Ungültiges channel-Feld: {tag}")

    items = channel.findall("item")
    if expected_episode_count is not None and len(items) != expected_episode_count:
        raise FeedValidationError("Die Episodenanzahl stimmt nicht überein.")

    seen_guids: set[str] = set()
    for item in items:
        title = (item.findtext("title") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        enclosure = item.find("enclosure")

        if not title:
            raise FeedValidationError("Eine Episode enthält keinen Titel.")
        if not guid:
            raise FeedValidationError(f"Episode {title!r} ohne GUID.")
        if guid in seen_guids:
            raise FeedValidationError(f"Doppelte GUID im Feed: {guid}")
        seen_guids.add(guid)

        if enclosure is None:
            raise FeedValidationError(f"Episode {title!r} ohne enclosure.")
        if not _is_https_url(enclosure.attrib.get("url", "")):
            raise FeedValidationError(
                f"Episode {title!r} ohne gültige Audio-URL."
            )
        if enclosure.attrib.get("type") != "audio/mpeg":
            raise FeedValidationError(
                f"Episode {title!r} verwendet nicht audio/mpeg."
            )

        length = enclosure.attrib.get("length", "")
        if not length.isdigit() or int(length) <= 0:
            raise FeedValidationError(
                f"Episode {title!r} enthält keine gültige Dateigröße."
            )

    return len(items)


def build_validated_feed(
    episodes: list[Episode] | tuple[Episode, ...],
    *,
    settings: FeedSettings,
) -> str:
    validate_settings(settings)
    xml_text = build_feed(
        episodes,
        feed_url=settings.feed_url,
        site_url=settings.site_url,
        image_url=settings.image_url,
        title=settings.title,
        description=settings.description,
        author=settings.author,
        language=settings.language,
        category=settings.category,
    )
    validate_feed_xml(xml_text, expected_episode_count=len(episodes))
    return xml_text


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def publish_pipeline_result(
    pipeline_result: PipelineResult,
    *,
    settings: FeedSettings,
    output_path: Path,
) -> FeedBuildResult:
    xml_text = build_validated_feed(
        list(pipeline_result.episodes),
        settings=settings,
    )
    write_text_atomic(output_path, xml_text)
    return FeedBuildResult(
        output_path=output_path,
        episode_count=len(pipeline_result.episodes),
        byte_count=len(xml_text.encode("utf-8")),
    )
