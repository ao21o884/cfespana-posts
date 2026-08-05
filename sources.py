# -*- coding: utf-8 -*-
"""
Data sources for the C.F. España post generator.

  ics_matches()     -> full season from the official Vereinsspielplan export
                       (Match center -> Verein -> Spielplan download)
  widget_scores()   -> recent results from the club's own SFV widget
                       (Match center -> Verein -> Club-Widget Konfiguration)

The main match center rejects automated requests, so it is never called here.
The widget is the endpoint the federation generates for the club to publish its
own data; we identify ourselves honestly and fetch at most twice a week.
"""
import os
import re
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
CLUB_V = 1368
ICS_DEFAULT = os.path.join(HERE, "Verein-v1368.ics")
WIDGET_URL = f"https://widget.football.ch/Widgets.aspx/v-{CLUB_V}/a-as/"
UA = "CFEspanaBern-Matchposts/1.0 (Vereinsnr 10336; c.f.espana1994@gmail.com)"

DOW = {0: "Mo", 1: "Di", 2: "Mi", 3: "Do", 4: "Fr", 5: "Sa", 6: "So"}


def _unescape(s):
    return (s.replace("\\\\n", "\n").replace("\\n", "\n")
             .replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")).strip()


def _field(block, key):
    m = re.search(rf"^{key}[^:]*:(.*)$", block, re.M)
    return m.group(1).strip() if m else ""


def _strip_team_suffix(name):
    """'C.F. España (4.)' -> 'C.F. España'"""
    return re.sub(r"\s*\((?:\d+\.|Sen\.\d+\+|Jun\.[^)]*)\)\s*$", "", name).strip()


def _venue(loc):
    """iCal writes 'Weissenstein\\, Bern - Fussballfeld Weissenstein 3'.
    We want 'Fussballfeld Weissenstein 3, Bern'."""
    loc = _unescape(loc)
    if " - " in loc:
        area, pitch = loc.split(" - ", 1)
        town = area.split(",")[-1].strip()
        return f"{pitch.strip()}, {town}" if town else pitch.strip()
    return loc


def ics_matches(path=None):
    path = path or ICS_DEFAULT
    raw = open(path, encoding="utf-8", newline="").read()
    raw = re.sub(r"\r?\n[ \t]", "", raw)          # RFC 5545 line unfolding
    out = []
    for block in re.findall(r"BEGIN:VEVENT\r?\n(.*?)\r?\nEND:VEVENT", raw, re.S):
        start = _field(block, "DTSTART")
        if "T" not in start:
            continue
        when = dt.datetime.strptime(start, "%Y%m%dT%H%M%S")
        desc = _unescape(_field(block, "DESCRIPTION"))
        summary = _unescape(_field(block, "SUMMARY"))
        head = desc.split("\n")[0].strip()
        uid = _field(block, "UID").split("@")[0]
        snr = re.search(r"Spielnummer\s+(\d+)", desc)

        rec = dict(dow=DOW[when.weekday()], date=when.strftime("%d.%m.%Y"),
                   time="" if when.strftime("%H:%M") == "00:00" else when.strftime("%H:%M"), venue=_venue(_field(block, "LOCATION")),
                   uid=uid, spielnummer=snr.group(1) if snr else None, score=None,
                   home_v=None, away_v=None)

        if head.startswith("Organisator:"):
            org = head.split("-", 1)[0].replace("Organisator:", "").strip()
            kat = re.search(r"(Jun\.[A-G])", head)
            rec.update(is_tournament=True, home=org, away="",
                       competition="Turnier",
                       label=f"Turnier {kat.group(1)}" if kat else summary.split(" - ")[0])
        else:
            if " - " not in summary:
                continue
            home, away = summary.split(" - ", 1)
            rec.update(is_tournament=False,
                       home=_strip_team_suffix(home), away=_strip_team_suffix(away),
                       competition=head)
        out.append(rec)
    out.sort(key=lambda r: (dt.datetime.strptime(r["date"], "%d.%m.%Y"), r["time"]))
    return out


# ---------------------------------------------------------------- results
DATE_LINE = re.compile(r"^(Mo|Di|Mi|Do|Fr|Sa|So)\s+(\d{2}\.\d{2}\.\d{4})$")
TIME_LINE = re.compile(r"^\d{2}:\d{2}$")


def widget_scores():
    """Return {spielnummer: '2:2'} plus {v_id: club name} for crest lookups."""
    import requests
    from bs4 import BeautifulSoup
    r = requests.get(WIDGET_URL, timeout=30, headers={"User-Agent": UA})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    vmap = {}
    for a in soup.find_all("a", href=True):
        m = re.search(r"/v-(\d+)/?$", a["href"])
        if m and a.get_text(strip=True):
            vmap[a.get_text(strip=True)] = int(m.group(1))

    lines = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]
    scores, i = {}, 0
    while i < len(lines):
        if TIME_LINE.match(lines[i]):
            blk = lines[i:i + 16]
            snr = next((re.search(r"Spielnummer\s+(\d+)", b) for b in blk
                        if "Spielnummer" in b), None)
            digits = [j for j, b in enumerate(blk) if re.fullmatch(r"\d{1,2}", b)]
            sc = None
            for j in digits:
                if j + 2 < len(blk) and blk[j + 1] == ":" and re.fullmatch(r"\d{1,2}", blk[j + 2]):
                    sc = f"{blk[j]}:{blk[j + 2]}"
                    break
            if snr and sc:
                scores[snr.group(1)] = sc
        i += 1
    return scores, vmap


def load_matches(ics_path=None, with_scores=False):
    ms = ics_matches(ics_path)
    if with_scores:
        try:
            scores, vmap = widget_scores()
            for m in ms:
                if m.get("spielnummer") in scores:
                    m["score"] = scores[m["spielnummer"]]
                m["home_v"] = vmap.get(m.get("home"))
                m["away_v"] = vmap.get(m.get("away"))
        except Exception as e:
            print(f"  ! widget unavailable, no scores this run: {e}")
    return ms


if __name__ == "__main__":
    ms = ics_matches()
    print(f"{len(ms)} events, {ms[0]['date']} .. {ms[-1]['date']}")
    for m in ms[:8]:
        print(" ", m["dow"], m["date"], m["time"],
              m.get("label") or f"{m['home']} – {m['away']}", "|", m["competition"],
              "|", m["venue"])
