"""Validiert die lokale public/feed.xml."""

from pathlib import Path

from maloney_feed.publisher import validate_feed_xml

ROOT = Path(__file__).resolve().parents[1]
FEED = ROOT / "public" / "feed.xml"


def main() -> None:
    if not FEED.exists():
        raise SystemExit(f"Feed nicht gefunden: {FEED}")

    xml_text = FEED.read_text(encoding="utf-8")
    count = validate_feed_xml(xml_text)

    print("=== FEED-VALIDIERUNG ERFOLGREICH ===")
    print(f"Datei: {FEED}")
    print(f"Episoden: {count}")
    print(f"Dateigröße: {len(xml_text.encode('utf-8'))} Byte")


if __name__ == "__main__":
    main()
