"""Erzeugt den echten lokalen Feed aus den aktuellen SRF-Daten."""

from pathlib import Path

from maloney_feed.pipeline import fetch_feed_episodes
from maloney_feed.publisher import FeedSettings, publish_pipeline_result

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "public" / "feed.xml"
PUBLIC_BASE_URL = "https://irwitzer.github.io/PhilipMaloney-feed/"
EPISODE_IMAGE_URLS = tuple(
    f"{PUBLIC_BASE_URL}episode-images/{number:02d}_Episodenbilder.png"
    for number in range(1, 12)
)
SETTINGS = FeedSettings(
    feed_url=f"{PUBLIC_BASE_URL}feed.xml",
    site_url=PUBLIC_BASE_URL,
    image_url=f"{PUBLIC_BASE_URL}podcast-cover.png",
    episode_image_urls=EPISODE_IMAGE_URLS,
    title="Philip Maloney Feed",
    description=(
        "Innovativer Podcast-Feed für aktuell bei SRF verfügbare "
        "Philip-Maloney-Episoden. Unabhängiges, nicht kommerzielles "
        "Fanprojekt ohne offizielle Verbindung zu SRF. Non-commercial. "
        "Folgen, die von SRF depubliziert werden, werden sofort aus dem "
        "Feed entfernt."
    ),
    author="Roger Graf / SRF",
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
