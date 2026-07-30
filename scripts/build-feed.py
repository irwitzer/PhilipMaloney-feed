"""Erzeugt den echten lokalen Feed aus den aktuellen SRF-Daten."""

from pathlib import Path

from maloney_feed.pipeline import fetch_feed_episodes
from maloney_feed.publisher import FeedSettings, publish_pipeline_result

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public" / "feed.xml"
SETTINGS = FeedSettings(
    feed_url="https://irwitzer.github.io/PhilipMaloney-feed/feed.xml",
    site_url="https://www.srf.ch/audio/maloney",
    image_url=(
        "https://irwitzer.github.io/"
        "PhilipMaloney-feed/podcast-cover.png"
    ),
)


def main() -> None:
    print("SRF-Katalog und Audioressourcen werden geladen ...")
    pipeline_result = fetch_feed_episodes(
        page_count=3,
        maximum_episodes=60,
        maximum_age_days=365,
        max_workers=4,
    )

    if pipeline_result.failures:
        print("Feed wird wegen SRF-Fehlern nicht ersetzt.")
        for failure in pipeline_result.failures:
            print(f"- {failure.episode_id}: {failure.reason}")
        raise SystemExit(1)

    built = publish_pipeline_result(
        pipeline_result,
        settings=SETTINGS,
        output_path=OUTPUT,
    )

    print()
    print("=== FEED ERFOLGREICH ERZEUGT ===")
    print(f"Ausgabedatei: {built.output_path}")
    print(f"Episoden: {built.episode_count}")
    print(f"Dateigröße: {built.byte_count} Byte")
    print(f"Katalogeinträge: {pipeline_result.catalog_count}")
    print(f"Nicht verfügbar: {pipeline_result.skipped_unavailable}")
    print(f"Zu alt: {pipeline_result.skipped_expired}")
    print(f"Ohne Audio: {pipeline_result.skipped_without_audio}")


if __name__ == "__main__":
    main()
