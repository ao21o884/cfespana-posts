# -*- coding: utf-8 -*-
"""
Data source for C.F. España matches.
Scrapes directly from matchcenter.fvbj-afbj.ch — no ICS file needed.
"""
import re
import datetime as dt
import requests
from bs4 import BeautifulSoup

URL = "https://matchcenter.fvbj-afbj.ch/default.aspx?v=1368&oid=6&lng=1&a=vs"

DOW_MAP = {
    "Mo": "Mo", "Di": "Di", "Mi": "Mi", "Do": "Do",
    "Fr": "Fr", "Sa": "Sa", "So": "So",
}

def _parse_date(s):
    """'So 09.08.2026' → ('So', '09.08.2026')"""
    m = re.match(r'(Mo|Di|Mi|Do|Fr|Sa|So)\s+(\d{2}\.\d{2}\.\d{4})', s.strip())
    if m:
        return m.group(1), m.group(2)
    return None, None

def _is_espana(name):
    return bool(re.search(r'espa[ñn]a', name, re.I))

def load_matches(url=URL):
    """Fetch and parse all C.F. España matches from the matchcenter web page."""
    try:
        r = requests.get(url, timeout=20,
                 headers={
                     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                     "Accept-Language": "de-CH,de;q=0.9,en;q=0.8",
                     "Referer": "https://matchcenter.fvbj-afbj.ch/",
                 })
        r.raise_for_status()
        html = r.text
    except Exception as e:
        print(f"  ! web fetch failed: {e} — falling back to ICS")
        return _load_from_ics()

    soup = BeautifulSoup(html, "html.parser")
    # Find the Vereinsspielplan section
    section = soup.find(string=re.compile("Vereinsspielplan"))
    if section is None:
        print("  ! Vereinsspielplan section not found — falling back to ICS")
        return _load_from_ics()

    # Get all text lines after that heading
    container = section.find_parent()
    while container and container.name not in ("div","section","td","body"):
        container = container.find_parent()
    if container is None:
        container = soup

    text = container.get_text(separator="\n")
    return _parse_text(text)


def _parse_text(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    matches = []
    cur_dow = cur_date = None
    i = 0

    # find start of schedule
    while i < len(lines):
        if lines[i] == "Vereinsspielplan":
            i += 1
            break
        i += 1

    time_re  = re.compile(r'^\d{2}:\d{2}$')
    date_re  = re.compile(r'^(Mo|Di|Mi|Do|Fr|Sa|So)\s+\d{2}\.\d{2}\.\d{4}$')
    tour_re  = re.compile(r'Turnier', re.I)
    spiel_re = re.compile(r'Spielnummer\s+(\d+)')
    jun_re   = re.compile(r'Jun\.([A-G])\b', re.I)

    while i < len(lines):
        line = lines[i]

        # Date header
        dow, date = _parse_date(line)
        if dow:
            cur_dow = dow; cur_date = date
            i += 1
            continue

        if cur_date is None:
            i += 1
            continue

        # Tournament block
        if tour_re.search(line) and "Junior" in line:
            # next line: Jun.X category
            jun_letter = ""
            peek = lines[i+1] if i+1 < len(lines) else ""
            jm = jun_re.search(peek)
            if jm:
                jun_letter = jm.group(1).upper()
                i += 1  # consume the Jun.X line

            # next lines: turnier name, Organisator:..., venue
            i += 1
            time_val = ""
            venue = ""
            organisator = ""
            # Look for optional time, then sub-category, then org, then venue
            for _ in range(8):
                if i >= len(lines): break
                l = lines[i]
                if time_re.match(l) and not time_val:
                    time_val = l; i += 1; continue
                if l.startswith("Organisator:"):
                    organisator = l.replace("Organisator:","").strip(); i += 1; continue
                if re.match(r'^Spielnummer', l): i += 1; break
                if re.search(r'Hauptplatz|Kunstrasen|Fussballfeld|Sportanlage|Terrain|platz', l, re.I):
                    venue = l; i += 1; continue
                if l.startswith("Bemerkung:"): i += 1; break
                if re.match(r'^(Mo|Di|Mi|Do|Fr|Sa|So)\s+\d', l): break
                if time_re.match(l): break
                if tour_re.search(l) and "Junior" in l: break
                i += 1

            matches.append({
                "dow": cur_dow, "date": cur_date, "time": time_val,
                "home": "C.F. España", "away": "",
                "competition": "Turnier",
                "label": f"Turnier Jun.{jun_letter}" if jun_letter else "Turnier",
                "venue": venue,
                "is_tournament": True,
                "spielnummer": None, "score": None,
                "home_v": None, "away_v": None,
                "uid": f"tour_{cur_date}_{jun_letter}_{time_val}",
            })
            continue

        # Time + match block
        if time_re.match(line):
            time_val = line; i += 1
            if i >= len(lines): break

            # Home team
            home = lines[i].strip(); i += 1
            # dash separator
            if i < len(lines) and lines[i] == "-":
                i += 1
            # Away team
            away = lines[i].strip() if i < len(lines) else ""; i += 1

            # Rest of block: competition, Spielnummer, venue
            competition = ""; spielnummer = None; venue = ""
            for _ in range(6):
                if i >= len(lines): break
                l = lines[i]
                if re.match(r'^(Mo|Di|Mi|Do|Fr|Sa|So)\s+\d', l): break
                if time_re.match(l): break
                if tour_re.search(l) and "Junior" in l: break
                sm = spiel_re.search(l)
                if sm:
                    spielnummer = sm.group(1)
                    # venue often on same line as Spielnummer or just after
                    # format: "Meisterschaft...\nSpielNr\nVENUE"
                    i += 1
                    if i < len(lines) and not time_re.match(lines[i]) and not re.match(r'^(Mo|Di|Mi|Do|Fr|Sa|So)', lines[i]):
                        venue = lines[i]; i += 1
                    break
                if re.search(r'Meisterschaft|Berner Cup|Liga|Cup', l, re.I) and not competition:
                    competition = l
                i += 1

            # Only keep if España involved
            if not (_is_espana(home) or _is_espana(away)):
                continue

            matches.append({
                "dow": cur_dow, "date": cur_date, "time": time_val,
                "home": home, "away": away,
                "competition": competition,
                "label": "",
                "venue": venue,
                "is_tournament": False,
                "spielnummer": spielnummer,
                "score": None,
                "home_v": None, "away_v": None,
                "uid": spielnummer or f"{cur_date}_{time_val}_{home[:8]}",
            })
            continue

        i += 1

    return matches


def _load_from_ics():
    """Fallback: parse Verein-v1368.ics when web scraping is unavailable."""
    import os
    HERE = os.path.dirname(os.path.abspath(__file__))
    ics_path = os.path.join(HERE, "Verein-v1368.ics")
    if not os.path.exists(ics_path):
        print("  ! ICS file not found either")
        return []

    try:
        text = open(ics_path, encoding="utf-8", errors="replace").read()
    except Exception as e:
        print(f"  ! ICS read error: {e}")
        return []

    US = "C.F. España"
    matches = []
    DOW_DE = {"MO":"Mo","TU":"Di","WE":"Mi","TH":"Do","FR":"Fr","SA":"Sa","SU":"So"}

    for event in re.split(r'BEGIN:VEVENT', text)[1:]:
        def get(key):
            m = re.search(rf'{key}[^:]*:(.*)', event)
            return m.group(1).strip() if m else ""

        dtstart = get("DTSTART")
        if len(dtstart) < 8:
            continue
        try:
            d = dt.date(int(dtstart[:4]), int(dtstart[4:6]), int(dtstart[6:8]))
        except ValueError:
            continue
        time_val = f"{dtstart[9:11]}:{dtstart[11:13]}" if len(dtstart) > 12 else ""

        summary  = get("SUMMARY")
        location = get("LOCATION")
        desc     = get("DESCRIPTION")
        uid      = get("UID")

        # day of week
        dow = DOW_DE.get(d.strftime("%A")[:2].upper(),
                         ["Mo","Di","Mi","Do","Fr","Sa","So"][d.weekday()])

        # Parse home/away from summary "Home - Away" or "Home\n-\nAway"
        parts = re.split(r'\s+-\s+', summary, maxsplit=1)
        if len(parts) == 2:
            home, away = parts[0].strip(), parts[1].strip()
        else:
            home, away = summary.strip(), ""

        if not (_is_espana(home) or _is_espana(away) or
                "turnier" in summary.lower() or "turnier" in desc.lower()):
            continue

        is_tour = "turnier" in summary.lower() or "turnier" in desc.lower()
        label = ""
        if is_tour:
            jm = re.search(r'Jun\.([A-G])\b', desc + summary, re.I)
            label = f"Turnier Jun.{jm.group(1).upper()}" if jm else "Turnier"

        competition = ""
        for line in desc.replace("\\n","\n").splitlines():
            if re.search(r'Meisterschaft|Berner Cup|Liga', line, re.I):
                competition = line.strip(); break

        spielnummer = ""
        sm = re.search(r'Spielnummer\s*(\d+)', desc)
        if sm:
            spielnummer = sm.group(1)

        matches.append({
            "dow": dow,
            "date": d.strftime("%d.%m.%Y"),
            "time": time_val,
            "home": home, "away": away,
            "competition": competition,
            "label": label,
            "venue": location,
            "is_tournament": is_tour,
            "spielnummer": spielnummer,
            "score": None,
            "home_v": None, "away_v": None,
            "uid": uid,
        })

    matches.sort(key=lambda m: (m["date"].split(".")[::-1], m["time"]))
    return matches


def week_scores(anchor=None):
    """Fetch current scores — stub, returns empty dict."""
    return {}
