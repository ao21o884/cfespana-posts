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
                         headers={"User-Agent": "CFEspana-Matchpost/2.0"})
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
    """Parse Verein-v1368.ics — robust parser for football.ch ICS format."""
    import os, re, datetime as dt
    HERE = os.path.dirname(os.path.abspath(__file__))
    ics_path = os.path.join(HERE, "Verein-v1368.ics")
    if not os.path.exists(ics_path):
        print("  ! ICS file not found")
        return []

    text = open(ics_path, encoding="utf-8", errors="replace").read()
    DOW = ["Mo","Di","Mi","Do","Fr","Sa","So"]

    matches = []
    for raw in re.split(r'BEGIN:VEVENT', text)[1:]:
        lines = raw.split('\n')

        # Unfold ICS lines (continuation lines start with space/tab)
        unfolded = []
        for l in lines:
            l = l.rstrip('\r')
            if l.startswith((' ', '\t')) and unfolded:
                unfolded[-1] += l[1:]
            else:
                unfolded.append(l)

        def get_field(key):
            for l in unfolded:
                if re.match(rf'{key}[;:]', l):
                    val = re.sub(rf'^{key}[^:]*:', '', l)
                    return val.replace('\\,', ',').replace('\\n', '\n').replace('\\\\n', '\n').strip()
            return ""

        # Date + time
        dtstart = get_field("DTSTART")
        m = re.search(r'(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})', dtstart)
        if not m:
            continue
        y,mo,d,h,mi = int(m.group(1)),int(m.group(2)),int(m.group(3)),int(m.group(4)),int(m.group(5))
        try:
            date_obj = dt.date(y, mo, d)
        except ValueError:
            continue
        time_val = f"{h:02d}:{mi:02d}"
        dow      = DOW[date_obj.weekday()]
        date_str = date_obj.strftime("%d.%m.%Y")
        uid      = get_field("UID")

        # SUMMARY: may be on one line "Home - Away" or split across two raw lines
        # Raw lines: "SUMMARY:Home (4.)" then "  - Away (3.)"
        home_raw = ""; away_raw = ""
        for i, l in enumerate(lines):
            l = l.rstrip('\r')
            if l.startswith('SUMMARY:'):
                home_raw = l[8:].strip()
                # Check next raw lines for away (start with spaces + "- ")
                for j in range(i+1, min(i+4, len(lines))):
                    nxt = lines[j].rstrip('\r')
                    m2 = re.match(r'^\s+-\s+(.*)', nxt)
                    if m2:
                        away_raw = m2.group(1).strip()
                        break
                    elif nxt and not nxt[0].isspace():
                        break
                break

        # Strip suffix like "(4.)" "(Sen.30+)" from names
        def clean(s):
            return re.sub(r'\s*\([^)]*\)\s*$', '', s).strip()

        home = clean(home_raw)
        away = clean(away_raw)

        # Tournament detection
        is_tour = "Turnier" in home_raw or "Turnier" in away_raw

        # Skip non-España non-tournament
        if not is_tour and not (_is_espana(home) or _is_espana(away)):
            continue

        # DESCRIPTION: get competition
        desc = get_field("DESCRIPTION")
        desc_lines = [l.strip() for l in desc.split('\n') if l.strip()]
        competition = ""
        for dl in desc_lines:
            if re.search(r'Meisterschaft|Berner Cup|Liga|Futsal|Cup', dl, re.I):
                competition = re.sub(r'\s+', ' ', dl).strip()
                break

        spielnummer = ""
        sm = re.search(r'Spielnummer\s+(\d+)', desc)
        if sm:
            spielnummer = sm.group(1)

        # LOCATION: "Place\, City - Fieldname"
        location = get_field("LOCATION")

        # Tournament label (Jun.E/F/G)
        label = ""
        if is_tour:
            raw_block = raw  # full event text
            jm = re.search(r'Jun\.([A-G])\b', raw_block, re.I)
            label = f"Turnier Jun.{jm.group(1).upper()}" if jm else "Turnier"
            home = "C.F. España"; away = ""

        matches.append({
            "dow": dow, "date": date_str, "time": time_val,
            "home": home, "away": away,
            "competition": competition, "label": label,
            "venue": location,
            "is_tournament": is_tour,
            "spielnummer": spielnummer,
            "score": None, "home_v": None, "away_v": None,
            "uid": uid,
        })

    matches.sort(key=lambda m: (m["date"].split(".")[::-1], m["time"]))
    return matches


def week_scores(anchor=None):
    """Fetch current scores — stub, returns empty dict."""
    return {}
