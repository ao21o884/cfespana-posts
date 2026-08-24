# -*- coding: utf-8 -*-
"""
Data source for C.F. España matches.

Calendari (per ordre):
  1. Vereinsspielplan en viu   -> matchcenter.refresh_calendar()
  2. cache/spielplan.json      -> última descàrrega correcta
  3. Verein-v1368.csv          -> còpia manual
  4. Verein-v1368.ics          -> últim recurs

Resultats: matchcenter.week_scores() (actes de partit / Spieltelegramm)

NOTA: la URL antiga .../a=vs&format=csv no existeix. El paràmetre format=csv
no forma part del matchcenter i sempre retorna 403; l'única exportació real
és 'Spielplan download' (a=kal), que genera un ICS sense marcadors.
"""
import csv, re, io, os, datetime as dt

import matchcenter
from matchcenter import week_scores  # noqa: F401  (el fa servir cfespana_post)

# User-Agent compartit (l'usa també cfespana_post.fetch_crest)
UA = matchcenter.UA

HERE      = os.path.dirname(os.path.abspath(__file__))
CSV_LOCAL = os.path.join(HERE, "Verein-v1368.csv")
ICS_LOCAL = os.path.join(HERE, "Verein-v1368.ics")

DOW = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _is_espana(s):
    return bool(re.search(r'espa[ñn]a', s or "", re.I))


def _parse_competition(spieltyp, bezeichnung):
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
    m = re.search(r'Jun\.([A-G])\b', bezeichnung or "", re.I)
    return f"Jun.{m.group(1).upper()}" if m else ""


def _sniff_delimiter(text):
    """El matchcenter exporta amb ';', però alguna còpia pot venir amb ','."""
    head = text.splitlines()[0] if text else ""
    return ';' if head.count(';') >= head.count(',') else ','


def _parse_csv_rows(text):
    """Parse the club CSV export into match dicts."""
    text = text.lstrip('\ufeff')
    reader = csv.DictReader(io.StringIO(text), delimiter=_sniff_delimiter(text))

    # Normalitza els noms de columna: minúscules i sense espais
    def col(row, *names):
        for n in names:
            for k, v in row.items():
                if k and k.strip().lower().replace(" ", "") == n.lower().replace(" ", ""):
                    return (v or "").strip()
        return ""

    matches = []
    for row in reader:
        spieltyp    = col(row, "SpielTyp", "Spieltyp")
        bezeichnung = col(row, "Bezeichnung")
        spielnummer = col(row, "Spielnummer")
        tag         = col(row, "TagKurz", "Tag")
        datum       = col(row, "Spieldatum", "Datum")
        zeit        = col(row, "Spielzeit", "Zeit")
        team_a      = col(row, "Teamname A", "TeamnameA", "Team A", "Heim")
        team_b      = col(row, "Teamname B", "TeamnameB", "Team B", "Gast")
        spielort    = col(row, "Spielort")
        sportanlage = col(row, "Sportanlage")
        ort         = col(row, "Ort")

        is_tour = "Turnier" in spieltyp

        if is_tour:
            home = "C.F. España"
            away = ""
            jl   = _junior_from_bezeichnung(bezeichnung)
            label = f"Turnier {jl}" if jl else "Turnier"
            if not _is_espana(team_a) and not _is_espana(team_b):
                continue
        else:
            home  = team_a
            away  = team_b
            label = ""
            if not (_is_espana(home) or _is_espana(away)):
                continue

        if sportanlage and ort:
            venue = f"{sportanlage}, {ort}"
        elif spielort:
            venue = spielort
        else:
            venue = ""

        competition = _parse_competition(spieltyp, bezeichnung)

        if datum:
            try:
                dp = datum.split(".")
                date_obj = dt.date(int(dp[2]), int(dp[1]), int(dp[0]))
                dow = DOW[date_obj.weekday()]
            except Exception:
                dow = tag
        else:
            dow = tag

        matches.append({
            "dow": dow, "date": datum, "time": zeit,
            "home": home, "away": away,
            "competition": competition, "label": label,
            "venue": venue, "is_tournament": is_tour,
            "spielnummer": spielnummer,
            "score": None, "home_v": None, "away_v": None,
            "uid": spielnummer or f"{datum}_{zeit}_{home[:6]}",
        })

    return matches


def _local_matches():
    """Calendari dels fitxers locals: CSV si es pot parsejar, si no l'ICS."""
    if os.path.exists(CSV_LOCAL):
        try:
            text = open(CSV_LOCAL, encoding="latin-1", errors="replace").read()
            matches = _parse_csv_rows(text)
            if matches:
                print(f"  · CSV local: {len(matches)} partits")
                return matches
            print("  ! el CSV local existeix però s'ha parsejat a 0 partits "
                  "— revisa els noms de columna")
        except Exception as e:
            print(f"  ! local CSV failed: {e}")
    return _load_from_ics()


def load_matches(offline=False):
    """
    Calendari complet = cache acumulat (web en viu) + fitxers locals.

    El matchcenter només publica partits d'avui endavant, tant al
    Vereinsspielplan com a 'Aktuelle Spiele'. El cache va acumulant tot el
    que s'ha vist, i els fitxers locals (CSV/ICS) tapen els forats
    d'històric que el cache encara no cobreix. Els partits del cache tenen
    prioritat, perquè són els més actualitzats.
    """
    if offline:
        web = matchcenter.cached_calendar()
    else:
        web = matchcenter.refresh_calendar()

    local = _local_matches()

    if not web:
        print(f"  · només fitxers locals: {len(local)} partits")
        return local

    merged = matchcenter.merge_matches(local, web)
    print(f"  ✓ calendari final: {len(merged)} partits "
          f"({len(web)} del cache, {len(local)} locals)")
    return merged


def _load_from_ics():
    """Parse Verein-v1368.ics as last resort."""
    if not os.path.exists(ICS_LOCAL):
        print("  ! ICS file not found")
        return []
    text = open(ICS_LOCAL, encoding="utf-8", errors="replace").read()
    matches = []
    for raw in re.split(r'BEGIN:VEVENT', text)[1:]:
        lines = raw.split('\n')
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

        dtstart = get_field("DTSTART")
        m = re.search(r'(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})', dtstart)
        if not m:
            continue
        y, mo, d, h, mi = (int(m.group(i)) for i in range(1, 6))
        try:
            date_obj = dt.date(y, mo, d)
        except ValueError:
            continue
        time_val = f"{h:02d}:{mi:02d}"
        dow      = DOW[date_obj.weekday()]
        date_str = date_obj.strftime("%d.%m.%Y")
        uid      = get_field("UID")

        home_raw = ""
        away_raw = ""
        for i, l in enumerate(lines):
            l = l.rstrip('\r')
            if l.startswith('SUMMARY:'):
                home_raw = l[8:].strip()
                for j in range(i + 1, min(i + 4, len(lines))):
                    nxt = lines[j].rstrip('\r')
                    m2 = re.match(r'^\s+-\s+(.*)', nxt)
                    if m2:
                        away_raw = m2.group(1).strip()
                        break
                    elif nxt and not nxt[0].isspace():
                        break
                break

        def clean(s):
            return re.sub(r'\s*\([^)]*\)\s*$', '', s).strip()

        home = clean(home_raw)
        away = clean(away_raw)
        is_tour = "Turnier" in home_raw or "Turnier" in away_raw
        if not is_tour and not (_is_espana(home) or _is_espana(away)):
            continue

        desc = get_field("DESCRIPTION")
        competition = ""
        for dl in [l.strip() for l in desc.split('\n') if l.strip()]:
            if re.search(r'Meisterschaft|Berner Cup|Liga|Cup', dl, re.I):
                competition = re.sub(r'\s+', ' ', dl).strip()
                break

        spielnummer = ""
        sm = re.search(r'Spielnummer\s+(\d+)', desc)
        if sm:
            spielnummer = sm.group(1)

        location = get_field("LOCATION")
        label = ""
        if is_tour:
            jm = re.search(r'Jun\.([A-G])\b', raw, re.I)
            label = f"Turnier Jun.{jm.group(1).upper()}" if jm else "Turnier"
            home = "C.F. España"
            away = ""

        matches.append({
            "dow": dow, "date": date_str, "time": time_val, "home": home, "away": away,
            "competition": competition, "label": label, "venue": location,
            "is_tournament": is_tour, "spielnummer": spielnummer,
            "score": None, "home_v": None, "away_v": None, "uid": uid,
        })

    matches.sort(key=lambda m: (m["date"].split(".")[::-1], m["time"]))
    print(f"  ✓ ICS ({len(matches)} partits)")
    return matches
