# -*- coding: utf-8 -*-
"""
C.F. España — automatic Instagram matchday / results post generator.

  python cfespana_post.py preview            # this week's fixture post
  python cfespana_post.py preview --results  # this week's results post
  python cfespana_post.py preview --week 2026-08-15

Data source : FVBJ match center (Vereinsspielplan, club id v=1368)
Crests      : blob.football.ch/logos/Verein/<Vereinsnr>.gif
              -> resolved by following the opponent's club page.
              If a crest cannot be resolved it is NEVER invented; a neutral
              monogram badge is drawn instead.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render      # noqa: E402
import sources     # noqa: E402

CLUB_NR = 10336
LOGO_URL = "https://blob.football.ch/logos/Verein/{nr}.gif"
CACHE = os.path.join(HERE, "cache")
CLUBS = os.path.join(HERE, "clubs.json")
US = "C.F. España"


# ---------------------------------------------------------------- scraping
# ---------------------------------------------------------------- crests
def club_numbers():
    """name -> Vereinsnr, from clubs.json"""
    try:
        return json.load(open(CLUBS, encoding="utf-8"))
    except Exception:
        return {}


def fetch_crest(v, name):
    """Download the official crest. Returns a path, or None — never a made-up logo."""
    if name.startswith(US):
        return os.path.join(HERE, "assets", "cfespana_big.png")
    nr = club_numbers().get(name)
    if not nr:
        print(f"  · no Vereinsnr for {name!r} — add it to clubs.json", file=sys.stderr)
        return None
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, f"{nr}.png")
    if os.path.exists(p):
        return p
    try:
        import io
        import requests
        from PIL import Image
        r = requests.get(LOGO_URL.format(nr=nr), timeout=30,
                         headers={"User-Agent": sources.UA})
        r.raise_for_status()
        Image.open(io.BytesIO(r.content)).convert("RGBA").save(p)
        return p
    except Exception as e:
        print(f"  ! no crest for {name}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------- selection
def d(m):
    return dt.datetime.strptime(m["date"], "%d.%m.%Y").date()


def week_window(anchor=None):
    """Monday 00:00 -> Sunday 23:59 of the week containing `anchor`."""
    a = anchor or dt.date.today()
    mon = a - dt.timedelta(days=a.weekday())
    return mon, mon + dt.timedelta(days=6)


def matches_in_week(all_m, anchor=None, include_tournaments=True):
    lo, hi = week_window(anchor)
    out = [m for m in all_m if lo <= d(m) <= hi]
    if not include_tournaments:
        out = [m for m in out if not m.get("is_tournament")]
    return sorted(out, key=lambda m: (d(m), m.get("time") or "00:00"))


def outcome(m):
    if not m.get("score"):
        return None
    try:
        a, b = (int(x) for x in m["score"].split(":"))
    except ValueError:
        return None
    us_home = m["home"].startswith(US)
    gf, ga = (a, b) if us_home else (b, a)
    return "W" if gf > ga else ("L" if gf < ga else "D")


# ---------------------------------------------------------------- captions
DAY = {"Mo": "Montag", "Di": "Dienstag", "Mi": "Mittwoch", "Do": "Donnerstag",
       "Fr": "Freitag", "Sa": "Samstag", "So": "Sonntag"}
def tidy_comp(c):
    """'Cup Berner Cup - Runde  1' -> 'Berner Cup - Runde 1'"""
    c = re.sub(r"^Cup\s+", "", c or "")
    return re.sub(r"\s{2,}", " ", c).strip()


TAGS = ("#CFEspaña #VamosEspaña #Spieltag #FussballBern #Bern #Amateurfussball "
        "#FVBJ #Matchday #Schweiz")


def caption_preview(ms):
    real = [m for m in ms if not m.get("is_tournament")]
    if len(real) == 1:
        m = real[0]
        opp = m["away"] if m["home"].startswith(US) else m["home"]
        where = "Heimspiel" if m["home"].startswith(US) else "Auswärtsspiel"
        L = ["🔴🟡 SPIELTAG! 🟡🔴", "",
             f"{where} gegen {opp} — wir zählen auf euch!", "",
             f"📅 {DAY.get(m['dow'], m['dow'])}, {m['date']}",
             f"⏰ {m['time']} Uhr",
             f"📍 {m['venue']}",
             f"🏆 {tidy_comp(m['competition'])}", ""]
    else:
        L = ["🔴🟡 UNSERE SPIELE DIESE WOCHE 🟡🔴", "",
             f"{len(ms)} Termine stehen an — kommt vorbei und unterstützt unsere Teams!", ""]
        last = None
        for m in ms:
            if m["date"] != last:
                L.append(f"📅 {DAY.get(m['dow'], m['dow'])}, {m['date']}")
                last = m["date"]
            if m.get("is_tournament"):
                L.append(f"   ⏰ {m['time']} · {m['label']} (Turnier) · {m['venue']}")
            else:
                L.append(f"   ⏰ {m['time']} · {m['home']} – {m['away']}")
                L.append(f"      📍 {m['venue']}")
        L.append("")
    L += ["Kommt zahlreich, macht Lärm und zeigt, was C.F. España ausmacht! 🙌", "",
          "¡Vamos España! 💥", "", TAGS]
    return "\n".join(L)


def caption_results(ms):
    L = ["🔴🟡 RESULTATE DER WOCHE 🟡🔴", ""]
    for m in ms:
        if m.get("is_tournament"):
            L.append(f"🏅 {m['label']} — Turnier (keine Resultate)")
        elif m.get("score"):
            ic = {"W": "✅", "D": "➖", "L": "❌"}.get(outcome(m), "⚽")
            L.append(f"{ic} {m['home']} {m['score']} {m['away']}")
        else:
            L.append(f"⏳ {m['home']} – {m['away']} (noch kein Resultat)")
    L += ["", "Danke an alle Spieler, Trainer und Fans für die Unterstützung! 🙌", "",
          "¡Vamos España! 💥", "", TAGS.replace("#Spieltag", "#Resultate")]
    return "\n".join(L)


# ---------------------------------------------------------------- build
def build(all_m, anchor=None, results=False, outdir=None, photo=None, fetch_crests=True):
    outdir = outdir or os.path.join(HERE, "out")
    os.makedirs(outdir, exist_ok=True)
    ms = matches_in_week(all_m, anchor)
    if not ms:
        print("No matches this week — nothing to post.")
        return None, None

    real = [m for m in ms if not m.get("is_tournament")]
    lo, hi = week_window(anchor)
    rng = f"{lo.strftime('%d.')} – {hi.strftime('%d. %B %Y')}"
    tag = ("results" if results else "preview") + "_" + lo.isoformat()
    png = os.path.join(outdir, f"cfespana_{tag}.png")

    if results:
        for m in ms:
            m["outcome"] = outcome(m)
        render.render_list(ms, png, title="RESULTATE", subtitle="UNSERE WOCHE",
                           daterange=rng, results=True, photo=photo)
        txt = caption_results(ms)
    elif len(real) == 1 and len(ms) == 1:
        m = dict(real[0])
        if fetch_crests:
            m["home_crest"] = fetch_crest(m.get("home_v"), m["home"])
            m["away_crest"] = fetch_crest(m.get("away_v"), m["away"])
        else:
            m["home_crest"] = os.path.join(HERE, "assets", "cfespana_big.png") if m["home"].startswith(US) else None
            m["away_crest"] = os.path.join(HERE, "assets", "cfespana_big.png") if m["away"].startswith(US) else None
        m["home_liga"] = m["away_liga"] = ""
        render.render_single(m, png, photo=photo)
        txt = caption_preview(ms)
    else:
        render.render_list(ms, png, title="SPIELPLAN", subtitle="SPIELE DER WOCHE",
                           daterange=rng, results=False, photo=photo)
        txt = caption_preview(ms)

    cap = png.replace(".png", ".txt")
    open(cap, "w", encoding="utf-8").write(txt)
    print(f"→ {png}\n→ {cap}")
    return png, cap




if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["preview", "results"], nargs="?", default="preview")
    p.add_argument("--week", help="any date inside the target week, YYYY-MM-DD")
    p.add_argument("--ics", help="path to the Vereinsspielplan .ics export")
    p.add_argument("--no-crests", action="store_true")
    p.add_argument("--photo", help="background photo (optional)")
    p.add_argument("--outdir")
    a = p.parse_args()
    anchor = dt.date.fromisoformat(a.week) if a.week else None
    ms = sources.load_matches(a.ics, with_scores=(a.cmd == "results"))
    build(ms, anchor=anchor, results=(a.cmd == "results"),
          outdir=a.outdir, photo=a.photo, fetch_crests=not a.no_crests)
