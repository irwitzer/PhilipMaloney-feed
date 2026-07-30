"""Validiert die lokale public/feed.xml und ihre referenzierten Ressourcen."""

from pathlib import Path

from maloney_feed.publisher import validate_feed_xml
from maloney_feed.remote_validation import validate_feed_resources

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
FEED = PUBLIC / "feed.xml"
PUBLIC_BASE_URL = "https://irwitzer.github.io/PhilipMaloney-feed/"


def main() -> None:
    if not FEED.exists():
        raise SystemExit(f"Feed nicht gefunden: {FEED}")

    xml_text = FEED.read_text(encoding="utf-8")
    episode_count = validate_feed_xml(xml_text)
    image_count, audio_count = validate_feed_resources(
        xml_text,
        public_dir=PUBLIC,
        public_base_url=PUBLIC_BASE_URL,
    )

    print("=== FEED-VALIDIERUNG ERFOLGREICH ===")
    print(f"Datei: {FEED}")
    print(f"Episoden: {episode_count}")
    print(f"Dateigröße: {len(xml_text.encode('utf-8'))} Byte")
    print(f"Lokale Feed-Bilder geprüft: {image_count}")
    print(f"Erreichbare Audioressourcen geprüft: {audio_count}")


if __name__ == "__main__":
    main()
