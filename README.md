# Philip Maloney Feed

Ein kleiner, inoffizieller RSS-Podcast-Feed für die Hörspielreihe **Philip Maloney** von SRF.

Das Projekt befindet sich aktuell im vollständigen Rewrite und wird von Grund auf neu aufgebaut.

## Ziel

Das Projekt soll einen öffentlich abonnierbaren Podcast-Feed erzeugen, der:

- alle aktuell bei SRF abspielbaren Philip-Maloney-Folgen enthält
- neue Folgen automatisch erkennt
- Vorschaufolgen erst aufnimmt, sobald eine Audiodatei verfügbar ist
- Folgen nach Ablauf ihrer Verfügbarkeit wieder entfernt
- mit möglichst vielen Podcast-Apps kompatibel ist
- vollständig über GitHub Actions und GitHub Pages betrieben wird

## Grundprinzipien

- keine Speicherung oder Spiegelung von Audiodateien
- keine Veränderung oder Neukodierung der Audiodateien
- keine Datenbank
- kein eigener Server
- keine Benutzeroberfläche
- keine Unterstützung weiterer Podcasts
- Playwright nur als Fallback
- kleine, klar getrennte Python-Module
- automatisierte Tests von Anfang an

## Funktionsweise

Der Feed verweist ausschließlich auf öffentlich bereitgestellte SRF-Audiodateien.

Eine Episode wird nur veröffentlicht, wenn mindestens folgende Angaben vorhanden sind:

- stabile SRF-Episoden-ID
- Titel
- Veröffentlichungsdatum
- SRF-Episodenseite
- erreichbare direkte Audio-URL
- tatsächlich erkannter Audioinhalt

Vorschaufolgen ohne Audio erscheinen noch nicht im Feed und werden bei späteren Läufen erneut geprüft.

Folgen bleiben höchstens 365 Tage ab ihrem SRF-Veröffentlichungsdatum im Feed.

## Geplante Technik

- Python 3.12
- `httpx`
- Playwright
- pytest
- Ruff
- uv
- GitHub Actions
- GitHub Pages

## Projektstruktur

```text
src/maloney_feed/
├── main.py
├── config.py
├── models.py
├── srf.py
├── feed.py
└── validation.py

tests/
public/
.github/workflows/