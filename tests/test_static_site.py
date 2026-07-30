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
