"""Öffentliche SRF-Schnittstellen des Projekts."""

from maloney_feed.srf_catalog import (
    CATALOG_URL,
    SHOW_ID,
    SrfCatalogClient,
    SrfCatalogEpisode,
    SrfSourceError,
    deduplicate_catalog_episodes,
    parse_catalog_item,
    parse_catalog_page,
)
from maloney_feed.srf_media import (
    SrfAudioResource,
    SrfMediaClient,
    attach_audio_resource,
    build_media_url,
    parse_media_composition,
)

__all__ = [
    "CATALOG_URL",
    "SHOW_ID",
    "SrfAudioResource",
    "SrfCatalogClient",
    "SrfCatalogEpisode",
    "SrfMediaClient",
    "SrfSourceError",
    "attach_audio_resource",
    "build_media_url",
    "deduplicate_catalog_episodes",
    "parse_catalog_item",
    "parse_catalog_page",
    "parse_media_composition",
]
