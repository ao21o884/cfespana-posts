# -*- coding: utf-8 -*-
"""
Data source for C.F. España matches.
Primary:  CSV export from matchcenter.fvbj-afbj.ch (Verein-v1368.csv)
Fallback: ICS calendar (Verein-v1368.ics)
"""
import csv, re, io, os, datetime as dt, requests

HERE    = os.path.dirname(os.path.abspath(__file__))
CSV_URL = "https://matchcenter.fvbj-afbj.ch/default.aspx?v=1368&oid=6&lng=1&a=vs&format=csv"
CSV_LOCAL = os.path.join(HERE, "Verein-v1368.csv")
ICS_LOCAL = os.path.join(HERE, "Verein-v1368.ics")

DOW = ["Mo","Di","Mi","Do","Fr","Sa","So"]

def _is_espana(s):
    return bool(re.search(r'espa[ñn]a', s or "", re.I))

def _parse_competition(spieltyp, bezeichnung):
    """Build a clean competition string from CSV columns."""
    s = spieltyp.strip()
    b = bezeichnung.strip()
    if "Turnier" in s:
        return "Turnier"
    if "Cup" in s:
        return f"Cup {b}" if b else s
    if "Meisterschaft" in s:
        return f"Meisterschaft {b}" if b else s
    return b or s

def _junior_from_bezeichnung(bezeichnung):
    """Extract Jun.E / Jun.F / Jun.G from Bezeichnung field."""
    m = re.search(r'Jun\.([A-G])\b', bezeichnung or "", re.I)
    return f"Jun.{m.group(1).upper()}" if m else ""

def _parse_csv_rows(text):
    """Parse semicolon-separated CSV into match dicts."""
    # Fix encoding (latin-1 special chars come as â€¦ in utf-8 misread)
    reader = csv.DictReader(io.StringIO(text), delimiter=';')
    matches = []
    for row in reader:
        spieltyp   = row.get("SpielTyp","").strip()
        bezeichnung= row.get("Bezeichnung","").strip()
        spielnummer= row.get("Spielnummer","").strip()
        tag        = row.get("TagKurz","").strip()
        datum      = row.get("Spieldatum","").strip()
        zeit       = row.get("Spielzeit","").strip()
        team_a     = row.get("Teamname A","").strip()
        team_b     = row.get("Teamname B","").strip()
        spielort   = row.get("Spielort","").strip()
        sportanlage= row.get("Sportanlage","").strip()
        ort        = row.get("Ort","").strip()
        feld       = row.get("Wettspielfeld","").strip()

        is_tour = "Turnier" in spieltyp

        # For tournaments, team_a is "Organisator: XY" and team_b lists teams
        if is_tour:
            home = "C.F. España"
            away = ""
            jl   = _junior_from_bezeichnung(bezeichnung)
            label = f"Turnier {jl}" if jl else "Turnier"
            # Only include if España is actually in the tournament
            if not _is_espana(team_a) and not _is_espana(team_b):
                continue
        else:
            home  = team_a
            away  = team_b
            label = ""
            if not (_is_espana(home) or _is_espana(away)):
                continue

        # Venue: "Sportanlage, Ort" — clean format
        if sportanlage and ort:
            venue = f"{sportanlage}, {ort}"
        elif spielort:
            venue = spielort
        else:
            venue = ""

        competition = _parse_competition(spieltyp, bezeichnung)

        # Parse date to get day-of-week
        if datum:
            try:
                d_parts = datum.split(".")
                date_obj = dt.date(int(d_parts[2]), int(d_parts[1]), int(d_parts[0]))
                dow = DOW[date_obj.weekday()]
            except Exception:
                dow = tag
        else:
            dow = tag

        matches.append({
            "dow":         dow,
            "date":        datum,
            "time":        zeit,
            "home":        home,
            "away":        away,
            "competition": competition,
            "label":       label,
            "venue":       venue,
            "is_tournament": is_tour,
            "spielnummer": spielnummer,
            "score":       None,
            "home_v":      None,
            "away_v":      None,
            "uid":         spielnummer or f"{datum}_{zeit}_{home[:6]}",
        })

    return matches


def load_matches():
    """Load matches — tries web CSV, then local CSV, then ICS."""

    # 1. Try fetching CSV from web
    try:
        r = requests.get(CSV_URL, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/csv,text/plain,*/*",
        })
        r.raise_for_status()
        text = r.content.decode("latin-1")
        matches = _parse_csv_rows(text)
        if matches:
            print(f"  ✓ CSV loaded from web ({len(matches)} matches)")
            return matches
    except Exception as e:
        print(f"  ! web CSV failed: {e}")

    # 2. Try local CSV file
    if os.path.exists(CSV_LOCAL):
        try:
            text = open(CSV_LOCAL, encoding="latin-1", errors="replace").read()
            matches = _parse_csv_rows(text)
            if matches:
                print(f"  ✓ CSV loaded from file ({len(matches)} matches)")
                return matches
        except Exception as e:
            print(f"  ! local CSV failed: {e}")

    # 3. Fallback to ICS
    print("  ! falling back to ICS")
    return _load_from_ics()


def _load_from_ics():
    """Parse Verein-v1368.ics as last resort."""
    if not os.path.exists(ICS_LOCAL):
        print("  ! ICS file not found"); return []
    text = open(ICS_LOCAL, encoding="utf-8", errors="replace").read()
    matches = []
    for raw in re.split(r'BEGIN:VEVENT', text)[1:]:
        lines = raw.split('\n')
        unfolded = []
        for l in lines:
            l = l.rstrip('\r')
            if l.startswith((' ','\t')) and unfolded:
                unfolded[-1] += l[1:]
            else:
                unfolded.append(l)
        def get_field(key):
            for l in unfolded:
                if re.match(rf'{key}[;:]', l):
                    val = re.sub(rf'^{key}[^:]*:', '', l)
                    return val.replace('\\,',',').replace('\\n','\n').replace('\\\\n','\n').strip()
            return ""
        dtstart = get_field("DTSTART")
        m = re.search(r'(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})', dtstart)
        if not m: continue
        y,mo,d,h,mi = int(m.group(1)),int(m.group(2)),int(m.group(3)),int(m.group(4)),int(m.group(5))
        try: date_obj = dt.date(y,mo,d)
        except ValueError: continue
        time_val = f"{h:02d}:{mi:02d}"
        dow = DOW[date_obj.weekday()]
        date_str = date_obj.strftime("%d.%m.%Y")
        uid = get_field("UID")
        home_raw=""; away_raw=""
        for i,l in enumerate(lines):
            l=l.rstrip('\r')
            if l.startswith('SUMMARY:'):
                home_raw=l[8:].strip()
                for j in range(i+1,min(i+4,len(lines))):
                    nxt=lines[j].rstrip('\r')
                    m2=re.match(r'^\s+-\s+(.*)',nxt)
                    if m2: away_raw=m2.group(1).strip(); break
                    elif nxt and not nxt[0].isspace(): break
                break
        def clean(s): return re.sub(r'\s*\([^)]*\)\s*$','',s).strip()
        home=clean(home_raw); away=clean(away_raw)
        is_tour="Turnier" in home_raw or "Turnier" in away_raw
        if not is_tour and not (_is_espana(home) or _is_espana(away)): continue
        desc=get_field("DESCRIPTION")
        competition=""
        for dl in [l.strip() for l in desc.split('\n') if l.strip()]:
            if re.search(r'Meisterschaft|Berner Cup|Liga|Cup',dl,re.I):
                competition=re.sub(r'\s+',' ',dl).strip(); break
        spielnummer=""
        sm=re.search(r'Spielnummer\s+(\d+)',desc)
        if sm: spielnummer=sm.group(1)
        location=get_field("LOCATION")
        label=""
        if is_tour:
            jm=re.search(r'Jun\.([A-G])\b',raw,re.I)
            label=f"Turnier Jun.{jm.group(1).upper()}" if jm else "Turnier"
            home="C.F. España"; away=""
        matches.append({"dow":dow,"date":date_str,"time":time_val,"home":home,"away":away,
            "competition":competition,"label":label,"venue":location,"is_tournament":is_tour,
            "spielnummer":spielnummer,"score":None,"home_v":None,"away_v":None,"uid":uid})
    matches.sort(key=lambda m:(m["date"].split(".")[::-1],m["time"]))
    return matches


def week_scores(anchor=None):
    """
    Fetch results from matchcenter 'Aktuelle Spiele' page.
    Returns dict: spielnummer -> {'score': 'X:Y', 'home_goals': X, 'away_goals': Y}
    """
    import re
    url = "https://matchcenter.fvbj-afbj.ch/default.aspx?v=1368&oid=6&lng=1&a=as"
    try:
        from bs4 import BeautifulSoup
        r = requests.get(url, timeout=20, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n")
    except Exception as e:
        print(f"  ! week_scores fetch failed: {e}")
        return {}

    scores = {}
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    i = 0
    while i < len(lines):
        line = lines[i]
        sm = re.search(r'Spielnummer\s+(\d+)', line)
        if sm:
            spielnr = sm.group(1)
            # Look backwards up to 10 lines for score "X : Y"
            for j in range(max(0, i-10), i):
                score_m = re.match(r'^(\d+)\s*:\s*(\d+)$', lines[j])
                if score_m:
                    hg, ag = int(score_m.group(1)), int(score_m.group(2))
                    scores[spielnr] = {
                        "score": f"{hg}:{ag}",
                        "home_goals": hg,
                        "away_goals": ag,
                    }
                    break
        i += 1
    print(f"  · scores found: {len(scores)}")
    return scores
