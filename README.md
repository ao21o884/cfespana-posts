# C.F. España — Instagram Post Generator

Reads the club's official fixture data, picks the current week, and renders a
ready-to-post Instagram image (1080×1350) plus a German caption.

## Data sources — and one important note

The FVBJ **match center blocks automated requests** ("Ein maschineller Zugriff ist
nicht erlaubt"). It is never called by this project. Instead:

| What | Where from | How often |
|---|---|---|
| Fixtures (whole season) | `Verein-v1368.ics` — Match center → *Verein → Spielplan download → Vereinsspielplan*, downloaded by hand in a browser | once per season |
| Results | the club's own SFV widget, `widget.football.ch/Widgets.aspx/v-1368/a-as/` | once per week |
| Crests | `blob.football.ch/logos/Verein/<Vereinsnr>.gif`, via `clubs.json` | cached forever |

Requests identify themselves honestly (see `sources.UA`). If football.ch offers a
proper club interface, swap `sources.py` and nothing else changes.

**Refresh the .ics** whenever the schedule changes (postponements, cup draws) —
roughly a couple of times per season.

## Layouts (chosen automatically)
| Situation | Layout |
|---|---|
| exactly 1 fixture that week | editorial poster — big date block, typographic fixture, kickoff + venue |
| 2 or more | `SPIELPLAN` table — one row per fixture, venue as subline |
| `results` mode | `RESULTATE` table — category as subline, score chip: win green, loss red, draw grey |

Junior tournaments never get a score — they render as `–`. Fixtures with no
kickoff time yet show `ZEIT OFFEN`.

## Crests
`clubs.json` maps club name → Vereinsnr. Only C.F. España, Pieterlen and
Schwarzenburg are filled in; add the rest as you meet them (the number is on each
club's match center page).

**All-or-nothing rule:** the one-match poster shows crests only if *both* clubs'
crests resolved. If either is missing, neither is drawn and the layout falls back
to pure typography — the C.F. España crest still sits top-right. Nothing is ever
invented.

## Usage
```bash
pip install pillow requests beautifulsoup4
python cfespana_post.py preview                    # this week's fixtures
python cfespana_post.py results                    # this week's results
python cfespana_post.py preview --week 2026-08-19  # a specific week
python cfespana_post.py preview --no-crests        # skip crest downloads
python sources.py                                  # sanity-check the .ics
```
Output lands in `out/` as a `.png` + `.txt` pair.

Scheduling and Instagram publishing: see **SETUP.md**.
