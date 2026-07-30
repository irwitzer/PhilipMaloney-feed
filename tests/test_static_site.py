"""Tests für den wiederhergestellten und erhöhten Hero-Bereich."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLIC = PROJECT_ROOT / "public"


def test_required_site_files_exist() -> None:
    for name in ("index.html", "styles.css", "app.js", "hero-noir.png"):
        assert (PUBLIC / name).is_file()


def test_hero_is_full_width_and_taller() -> None:
    css = (PUBLIC / "styles.css").read_text(encoding="utf-8")

    assert 'url("hero-noir.png")' in css
    assert "background-position: center 35%;" in css
    assert "background-size: cover;" in css
    assert css.count("min-height: 880px;") == 2


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
