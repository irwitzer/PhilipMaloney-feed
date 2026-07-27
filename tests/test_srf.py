"""Kompatibilitätstest für die öffentliche SRF-Fassade."""

from maloney_feed.srf import (
    SrfCatalogClient,
    SrfMediaClient,
    build_media_url,
)


def test_public_srf_facade_exports_clients() -> None:
    assert SrfCatalogClient is not None
    assert SrfMediaClient is not None
    assert "onlyChapters=true" in build_media_url(
        "urn:srf:audio:test"
    )
