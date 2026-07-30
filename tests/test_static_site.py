"""Tests für getrennte Desktop- und Mobil-Hero-Assets."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC = PROJECT_ROOT / "public"


def test_required_site_files_exist() -> None:
    for name in (
        "index.html",
        "styles.css",
        "app.js",
        "hero-noir.png",
        "hero-noir-desktop.png",
    ):
        assert (PUBLIC / name).is_file()


def test_desktop_uses_the_wide_hero_asset() -> None:
    css = (PUBLIC / "styles.css").read_text(encoding="utf-8")

    desktop_rule = css.split("@media (max-width: 1120px)", maxsplit=1)[0]

    assert 'url("hero-noir-desktop.png")' in desktop_rule
    assert "background-size: cover;" in desktop_rule
    assert "min-height: 880px;" in desktop_rule


def test_tablet_and_mobile_keep_the_existing_hero_asset() -> None:
    css = (PUBLIC / "styles.css").read_text(encoding="utf-8")

    responsive_rules = css.split("@media (max-width: 1120px)", maxsplit=1)[1]

    assert responsive_rules.count('url("hero-noir.png")') >= 2
    assert 'url("hero-noir-desktop.png")' not in responsive_rules


def test_main_hero_actions_are_preserved() -> None:
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")

    assert "Feed XML öffnen" not in html
    assert "Feed abonnieren" in html
    assert "Auf GitHub ansehen" in html
    assert 'id="copy-feed"' in html


def test_header_monogram_is_preserved() -> None:
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")

    assert "brand-monogram" in html
    assert "brand-title" in html


def test_strong_mobile_scroll_reset_is_preserved() -> None:
    javascript = (PUBLIC / "app.js").read_text(encoding="utf-8")

    assert 'history.scrollRestoration = "manual"' in javascript
    assert "document.documentElement.scrollTop = 0" in javascript
    assert "document.body.scrollTop = 0" in javascript
    assert "requestAnimationFrame(forcePageTop)" in javascript
    assert 'window.addEventListener("pageshow", schedulePageTopReset)' in javascript
    assert "schedulePageTopReset();" in javascript


def test_header_contains_only_the_brand() -> None:
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")

    header = html.split('<header class="site-header">', maxsplit=1)[1].split(
        "</header>",
        maxsplit=1,
    )[0]

    assert '<a class="brand"' in header
    assert "<nav" not in header
    assert "Über den Feed" not in header
    assert ">Episoden<" not in header
    assert ">Abonnieren<" not in header
    assert ">GitHub<" not in header


def test_feature_icon_pngs_exist_and_are_referenced() -> None:
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")

    icon_names = [
        "01_MaloneyIcons.png",
        "02_MaloneyIcons.png",
        "03_MaloneyIcons.png",
        "04_MaloneyIcons.png",
        "05_MaloneyIcons.png",
    ]

    for icon_name in icon_names:
        assert (PUBLIC / "icons" / icon_name).is_file()
        assert f'src="icons/{icon_name}"' in html

    assert html.count('class="feature-icon feature-icon-image"') == 5


def test_feature_cards_have_consistent_content_and_links() -> None:
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")
    css = (PUBLIC / "styles.css").read_text(encoding="utf-8")

    assert "<h2>Aktuelle Episoden</h2>" in html
    assert '<strong id="episode-count">–</strong> Episoden' in html
    assert "<h2>Episodenübersicht</h2>" in html

    assert 'href="https://www.srf.ch/audio/maloney"' in html
    assert 'href="https://github.com/irwitzer/PhilipMaloney-feed"' in html
    assert 'href="https://github.com/irwitzer/PhilipMaloney-feed/actions"' in html

    assert html.count('class="stat-card stat-card-info"') == 2
    assert html.count('class="stat-card stat-card-link"') == 3

    assert ".episode-total" in css
    assert ".stat-card-link" in css
    assert "min-height: 2.6em;" in css


def test_feature_card_text_is_valid_utf8() -> None:
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")

    expected_texts = (
        "Tägliche Aktualisierung",
        "Episodenübersicht",
        "Alle derzeit verfügbaren Folgen des Philip-Maloney-Hörspiels.",
        "Der Feed wird automatisch geprüft und bei neuen Folgen erweitert.",
        "Alle verfügbaren Philip-Maloney-Folgen direkt auf der offiziellen SRF-Seite.",
        "Offen, transparent und zuverlässig über GitHub Pages bereitgestellt.",
        "Jeder neue Feed wird vor der Veröffentlichung technisch geprüft.",
    )

    for expected in expected_texts:
        assert expected in html

    broken_markers = (
        "Ã",
        "Â",
        "â€“",
        "â€”",
    )
    assert not any(marker in html for marker in broken_markers)


def test_how_section_uses_png_icons() -> None:
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")
    assert "<h2>So geht das!</h2>" in html
    assert "06_SoGehtDas_1.png" in html
    assert "07_SoGehtDas_2.png" in html
    assert "08_SoGehtDas_3.png" in html
    assert html.count('class="step-icon step-icon-image"') == 3


def test_both_subscribe_buttons_copy_the_feed_url() -> None:
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")
    javascript = (PUBLIC / "app.js").read_text(encoding="utf-8")

    assert 'id="subscribe-button"' in html
    assert 'id="subscribe-button-secondary"' in html
    assert 'id="copy-status"' in html
    assert 'id="secondary-copy-status"' in html
    assert html.count('href="#"') == 2

    assert 'querySelector("#subscribe-button")' in javascript
    assert 'querySelector("#subscribe-button-secondary")' in javascript
    assert "event.preventDefault()" in javascript
    assert "navigator.clipboard.writeText(PUBLIC_FEED_URL)" in javascript
    assert (
        "Feed-URL kopiert. Füge sie jetzt in deine Podcast-App ein."
        in javascript
    )
