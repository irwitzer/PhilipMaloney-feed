"""Prüft lokale Feed-Bilder und die Erreichbarkeit externer Audiodateien."""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET

import httpx

ITUNES_NAMESPACE = "http://www.itunes.com/dtds/podcast-1.0.dtd"


class RemoteResourceValidationError(RuntimeError):
    """Eine im Feed referenzierte Ressource ist nicht erreichbar oder ungültig."""


def _itunes_tag(name: str) -> str:
    return f"{{{ITUNES_NAMESPACE}}}{name}"


def _parse_feed(xml_text: str) -> ET.Element:
    try:
        return ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RemoteResourceValidationError(
            "Ressourcenprüfung abgebrochen: Feed ist kein gültiges XML."
        ) from exc


def collect_image_urls(xml_text: str) -> tuple[str, ...]:
    """Liest alle eindeutigen iTunes-Bild-URLs aus Channel und Episoden."""
    root = _parse_feed(xml_text)
    channel = root.find("channel")
    if channel is None:
        raise RemoteResourceValidationError("Feed enthält keinen channel.")

    urls: list[str] = []
    channel_image = channel.find(_itunes_tag("image"))
    if channel_image is not None:
        href = (channel_image.attrib.get("href") or "").strip()
        if href:
            urls.append(href)

    for item in channel.findall("item"):
        episode_image = item.find(_itunes_tag("image"))
        if episode_image is None:
            continue
        href = (episode_image.attrib.get("href") or "").strip()
        if href:
            urls.append(href)

    return tuple(dict.fromkeys(urls))


def collect_audio_urls(xml_text: str) -> tuple[str, ...]:
    """Liest alle eindeutigen Enclosure-URLs aus dem Feed."""
    root = _parse_feed(xml_text)
    urls: list[str] = []

    for enclosure in root.findall("./channel/item/enclosure"):
        url = (enclosure.attrib.get("url") or "").strip()
        if url:
            urls.append(url)

    return tuple(dict.fromkeys(urls))


def validate_local_image_assets(
    xml_text: str,
    *,
    public_dir: Path,
    public_base_url: str,
) -> tuple[Path, ...]:
    """Prüft, ob eigene Feed-Bilder im veröffentlichten public-Ordner existieren."""
    base = public_base_url.rstrip("/") + "/"
    checked: list[Path] = []

    for image_url in collect_image_urls(xml_text):
        if not image_url.startswith(base):
            raise RemoteResourceValidationError(
                f"Feed-Bild liegt nicht unter der eigenen öffentlichen URL: {image_url}"
            )

        relative_url = image_url.removeprefix(base)
        parsed = urlparse(relative_url)
        relative_path = Path(unquote(parsed.path))

        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise RemoteResourceValidationError(
                f"Ungültiger lokaler Bildpfad im Feed: {image_url}"
            )

        image_path = public_dir / relative_path
        if not image_path.is_file():
            raise RemoteResourceValidationError(
                f"Feed-Bild fehlt im public-Ordner: {image_path}"
            )
        if image_path.stat().st_size <= 0:
            raise RemoteResourceValidationError(
                f"Feed-Bild ist leer: {image_path}"
            )

        checked.append(image_path)

    if not checked:
        raise RemoteResourceValidationError("Feed enthält kein iTunes-Bild.")

    return tuple(dict.fromkeys(checked))


def _check_audio_url(url: str, timeout_seconds: float) -> None:
    headers = {
        "User-Agent": "PhilipMaloney-feed-validator/1.0",
        "Accept": "audio/mpeg,*/*;q=0.1",
    }

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=timeout_seconds,
            headers=headers,
        ) as client:
            response = client.head(url)

            if response.status_code in {403, 405}:
                response = client.get(
                    url,
                    headers={**headers, "Range": "bytes=0-0"},
                )

            response.raise_for_status()

            content_type = response.headers.get("content-type", "").lower()
            if content_type and not (
                content_type.startswith("audio/")
                or content_type.startswith("application/octet-stream")
            ):
                raise RemoteResourceValidationError(
                    f"Unerwarteter Content-Type für Audio-URL {url}: {content_type}"
                )
    except RemoteResourceValidationError:
        raise
    except httpx.HTTPError as exc:
        raise RemoteResourceValidationError(
            f"Audio-URL nicht erreichbar: {url} ({exc})"
        ) from exc


def validate_audio_urls(
    urls: Iterable[str],
    *,
    max_workers: int = 6,
    timeout_seconds: float = 20.0,
) -> int:
    """Prüft alle Audio-URLs parallel, ohne die vollständigen MP3s herunterzuladen."""
    unique_urls = tuple(dict.fromkeys(urls))
    if not unique_urls:
        raise RemoteResourceValidationError("Feed enthält keine Audio-URLs.")
    if max_workers < 1:
        raise ValueError("max_workers muss mindestens 1 sein.")

    failures: list[str] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_check_audio_url, url, timeout_seconds): url
            for url in unique_urls
        }

        for future in as_completed(futures):
            url = futures[future]
            try:
                future.result()
            except RemoteResourceValidationError as exc:
                failures.append(f"{url}: {exc}")

    if failures:
        details = "\n".join(f"- {failure}" for failure in sorted(failures))
        raise RemoteResourceValidationError(
            f"{len(failures)} Audioressource(n) nicht erreichbar:\n{details}"
        )

    return len(unique_urls)


def validate_feed_resources(
    xml_text: str,
    *,
    public_dir: Path,
    public_base_url: str,
    max_workers: int = 6,
    timeout_seconds: float = 20.0,
) -> tuple[int, int]:
    """Prüft eigene Bilder lokal und sämtliche Audio-URLs extern."""
    image_paths = validate_local_image_assets(
        xml_text,
        public_dir=public_dir,
        public_base_url=public_base_url,
    )
    audio_count = validate_audio_urls(
        collect_audio_urls(xml_text),
        max_workers=max_workers,
        timeout_seconds=timeout_seconds,
    )
    return len(image_paths), audio_count
