"""Kleiner manueller Live-Test für die SRF-End-to-End-Pipeline."""

from maloney_feed.pipeline import fetch_feed_episodes


def main() -> None:
    result = fetch_feed_episodes(
        page_count=1,
        maximum_episodes=5,
        max_workers=4,
    )

    print()
    print("=== SRF LIVE-TEST ===")
    print(f"Katalogeinträge: {result.catalog_count}")
    print(f"Feedfähige Episoden: {len(result.episodes)}")
    print(f"Nicht verfügbar: {result.skipped_unavailable}")
    print(f"Zu alt: {result.skipped_expired}")
    print(f"Ohne Audio: {result.skipped_without_audio}")
    print(f"Fehler: {len(result.failures)}")
    print()

    for episode in result.episodes:
        print(f"- {episode.published_at.date()} | {episode.title}")
        print(f"  {episode.audio_url}")

    if result.failures:
        print()
        print("Fehlerdetails:")
        for failure in result.failures:
            print(
                f"- {failure.episode_id} | "
                f"{failure.title}: {failure.reason}"
            )


if __name__ == "__main__":
    main()
