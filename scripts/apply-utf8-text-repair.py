from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    PROJECT_ROOT / "public" / "index.html",
    PROJECT_ROOT / "public" / "styles.css",
    PROJECT_ROOT / "public" / "app.js",
    PROJECT_ROOT / "tests" / "test_static_site.py",
]

REPLACEMENTS = {
    "\u00c3\u00a4": "\u00e4",
    "\u00c3\u00b6": "\u00f6",
    "\u00c3\u00bc": "\u00fc",
    "\u00c3\u0084": "\u00c4",
    "\u00c3\u0096": "\u00d6",
    "\u00c3\u009c": "\u00dc",
    "\u00c3\u009f": "\u00df",
    "\u00e2\u0080\u0093": "\u2013",
    "\u00e2\u0080\u0094": "\u2014",
    "\u00e2\u0080\u009e": "\u201e",
    "\u00e2\u0080\u009c": "\u201c",
    "\u00e2\u0080\u009d": "\u201d",
    "\u00e2\u0080\u00a6": "\u2026",
    "\u00c2\u00b7": "\u00b7",
}

BAD_MARKERS = tuple(REPLACEMENTS)


def read_utf8(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def repair_text(text: str) -> str:
    for broken, correct in REPLACEMENTS.items():
        text = text.replace(broken, correct)
    return text


def main() -> None:
    changed: list[Path] = []

    for path in TARGETS:
        if not path.is_file():
            raise FileNotFoundError(f"Required file is missing: {path}")

        original = read_utf8(path)
        repaired = repair_text(original)

        if any(marker in repaired for marker in BAD_MARKERS):
            raise RuntimeError(f"Encoding repair incomplete: {path}")

        if repaired != original:
            path.write_text(repaired, encoding="utf-8", newline="\n")
            changed.append(path)

    test_path = PROJECT_ROOT / "tests" / "test_static_site.py"
    tests = read_utf8(test_path)

    test_block = r