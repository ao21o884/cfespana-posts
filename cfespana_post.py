# -*- coding: utf-8 -*-
"""
C.F. España — automatic Instagram matchday / results post generator.

  python cfespana_post.py preview            # this week's fixture post
  python cfespana_post.py results            # this week's results post
  python cfespana_post.py preview --week 2026-08-15

Data source : calendari local (CSV/ICS) + resultats via matchcenter.py
Crests      : blob.football.ch/logos/Verein/<Vereinsnr>.gif
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


def _runde(comp):
    m = re.search(r'Runde\s*(\d+)', comp or "", re.I)
    return int(m.group(1)) if m else None


def _liga_short(comp):
    m = re.search(r'(\d+)\.\s*Liga', comp or "", re.I)
    if m:
        return f"{m.group(1)}. Liga"
    if "Senioren 30" in (comp or ""):
        return "Senioren 30+"
    if "Senioren 40" in (comp or ""):
        return "Senioren 40+"
    if "Berner Cup" in (comp or ""):
        return "Berner Cup"
    return tidy_comp(comp)


def _match_context(m):
    runde = _runde(m.get("competition", ""))
    liga  = _liga_short(m.get("competition", ""))
    opp   = m["away"] if m["home"].startswith(US) else m["home"]
    home  = m["home"].startswith(US)
    if runde == 1:
        ctx = f"Die Saison beginnt! Runde 1 in der {liga} — der erste Schritt in eine neue Saison."
    elif runde == 2:
        ctx = f"Runde 2 in der {liga} — die Chance, früh ein Zeichen zu setzen."
    elif runde:
        ctx = f"Runde {runde} in der {liga} — jeder Punkt zählt."
    else:
        ctx = f"Ein wichtiges Spiel in der {liga}."
    if home:
        ctx += f" Heute empfangen wir {opp} auf eigenem Rasen."
    else:
        ctx += f" Auswärts bei {opp} — Zeit zu zeigen, was wir können."
    return ctx


def caption_preview(ms):
    real = [m for m in ms if not m.get("is_tournament")]
    if len(real) == 1:
        m   = real[0]
        ctx = _match_context(m)
        ort = render.fmt_venue(m.get("venue", ""))
        L = [
            "⚽ MATCH DAY", "",
            ctx, "",
            f"📅 {DAY.get(m['dow'], m['dow'])}, {m['date']}",
            f"⏰ {m['time']} Uhr",
            f"📍 {ort}", "",
            "Kommt vorbei, macht Lärm und zeigt, was C.F. España ausmacht! 🔴🟡",
            "", "¡Vamos España!",
        ]
    else:
        n_real = len(real)
        n_tour = len([m for m in ms if m.get("is_tournament")])
        intro  = f"Eine volle Woche steht bevor — {n_real} Pflichtspiele"
        if n_tour:
            intro += f" und {n_tour} Turnier{'e' if n_tour > 1 else ''} für unsere Junioren"
        intro += ". Kommt vorbei und unterstützt unsere Teams!"
        L = ["⚽ UNSERE WOCHE", "", intro, ""]
        last = None
        for m in ms:
            if m["date"] != last:
                L.append(f"📅 {DAY.get(m['dow'], m['dow'])}, {m['date']}")
                last = m["date"]
            if m.get("is_tournament"):
                L.append(f"   ⏰ {m['time']} · {m.get('label','Turnier')} (Turnier)")
            else:
                ort = render.fmt_venue(m.get("venue", ""))
                L.append(f"   ⏰ {m['time']} · {m['home']} – {m['away']}")
                if ort:
                    L.append(f"      📍 {ort}")
        L += ["", "¡Vamos España! 🔴🟡"]
    return "\n".join(L)


def caption_results(ms):
    scored = [m for m in ms if not m.get("is_tournament") and m.get("score")]
    wins   = [m for m in scored if outcome(m) == "W"]
    losses = [m for m in scored if outcome(m) == "L"]
    draws  = [m for m in scored if outcome(m) == "D"]
    if wins and not losses and not draws:
        mood = f"Was für eine Woche! {len(wins)} Sieg{'e' if len(wins)>1 else ''} — der Verein läuft!"
    elif losses and not wins and not draws:
        mood = "Eine schwierige Woche liegt hinter uns. Aber wir stehen auf, analysieren und kommen stärker zurück."
    elif wins and losses:
        mood = (f"{len(wins)} Sieg{'e' if len(wins)>1 else ''}, "
                f"{len(losses)} Niederlage{'n' if len(losses)>1 else ''} — "
                f"gemischte Gefühle, aber der Kampfgeist bleibt.")
    elif draws:
        mood = "Unentschieden liegen in der Luft — nah dran, aber noch nicht ganz. Weiter so!"
    else:
        mood = "Die Resultate der Woche — Danke an alle die dabei waren!"
    L = ["📊 RESULTATE DER WOCHE", "", mood, ""]
    for m in ms:
        if m.get("is_tournament"):
            continue
        oc = outcome(m)
        if m.get("score"):
            ic   = {"W": "✅", "D": "➖", "L": "❌"}.get(oc, "⚽")
            liga = _liga_short(m.get("competition", ""))
            L.append(f"{ic} {m['home']} {m['score']} {m['away']}  ({liga})")
        else:
            L.append(f"⏳ {m['home']} – {m['away']} (noch kein Resultat)")
    L += ["", "Danke an alle Spieler, Trainer und Fans! 🙌", "", "¡Vamos España! 🔴🟡"]
    return "\n".join(L)


# Photo background — stored in assets/pitch.jpg
PITCH = os.path.join(HERE, "assets", "pitch.jpg")

MAX_PER_POST = 6   # max rows per image; more → split into two posts


# Marc quadrat amb els laterals difuminats: el cartell és 1080x1350 i
# Instagram el retalla o el mostra amb bandes. Amplia el llenç a 1350x1350
# i omple els costats amb una versió desenfocada i enfosquida del mateix
# cartell, com als posts anteriors.
# Marc quadrat amb els laterals difuminats.
#
# Aquest és l'algorisme original (recuperat de la conversa on es va dissenyar):
# el cartell de 1080x1350 s'ESTIRA a 1350x1350 — deformant-lo a propòsit —
# es difumina amb radi 40 i s'enfosqueix al 50%. Després s'hi enganxa el
# cartell original centrat. Un retall proporcional amb zoom dona un
# enquadrament diferent i no s'assembla.
#
# Vivia a render.py com add_instagram_sides() i es va perdre en una
# repujada del fitxer. Ara viu aquí perquè no es torni a perdre.
BLURRED_SIDES = True
SIDE_CANVAS   = 1350
SIDE_BLUR     = 40
SIDE_DIM      = 0.5


def add_blurred_sides(png_path, canvas=SIDE_CANVAS,
                      blur=SIDE_BLUR, dim=SIDE_DIM, **kw):
    """Amplia el PNG a un llenç quadrat amb els costats difuminats. In-place."""
    from PIL import Image, ImageFilter, ImageEnhance

    img = Image.open(png_path).convert("RGB")
    w, h = img.size
    if w >= canvas:
        return png_path                      # ja és prou ample

    bg = img.resize((canvas, canvas), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=blur))
    bg = ImageEnhance.Brightness(bg).enhance(dim)

    bg.paste(img, ((canvas - w) // 2, (canvas - h) // 2))
    bg.save(png_path, quality=95)
    return png_path


def dedup_tournaments(matches):
    """Remove duplicate tournament entries: same day + same junior letter."""
    seen = set()
    out  = []
    for m in matches:
        if m.get("is_tournament"):
            label  = m.get("label", "") or m.get("competition", "")
            mt     = re.search(r'Jun(?:ioren)?[\.\s]*([A-G])', label, re.I)
            letter = mt.group(1).upper() if mt else "?"
            key    = (m["date"], letter)
            if key in seen:
                continue
            seen.add(key)
        out.append(m)
    return out


# ---------------------------------------------------------------- build
def build(all_m, anchor=None, results=False, outdir=None, photo=None, fetch_crests=True):
    outdir = outdir or os.path.join(HERE, "out")
    os.makedirs(outdir, exist_ok=True)
    ms = matches_in_week(all_m, anchor)
    if not ms:
        print("No matches this week — nothing to post.")
        return None, None

    ms = dedup_tournaments(ms)

    real = [m for m in ms if not m.get("is_tournament")]
    lo, hi = week_window(anchor)
    rng = f"{lo.strftime('%d.')} – {hi.strftime('%d. %B %Y')}"
    tag = ("results" if results else "preview") + "_" + lo.isoformat()
    png = os.path.join(outdir, f"cfespana_{tag}.png")

    def team_label(m):
        comp = m.get("competition", "")
        if "Junioren D" in comp: return "Junioren D"
        if "Junioren E" in comp: return "Junioren E"
        if "Senioren 30" in comp: return "Senioren 30+"
        if "Senioren 40" in comp: return "Senioren 40+"
        if "Senioren 50" in comp: return "Senioren 50+"
        return "1. Mannschaft"

    def do_render(match_list, out_path, title, subtitle, is_results):
        render.render_list_photo(match_list, out_path, photo_path=PITCH,
                                 title=title, subtitle=subtitle,
                                 daterange=rng, results=is_results)
        if BLURRED_SIDES:
            add_blurred_sides(out_path)

    def save_cap(txt, base_png):
        cap = base_png.replace(".png", ".txt")
        open(cap, "w", encoding="utf-8").write(txt)
        print(f"→ {base_png}\n→ {cap}")
        return base_png, cap

    def maybe_split(match_list, title, subtitle, is_results, txt):
        """Render one or two images depending on list length."""
        if len(match_list) <= MAX_PER_POST:
            do_render(match_list, png, title, subtitle, is_results)
            return save_cap(txt, png)
        mid   = (len(match_list) + 1) // 2
        png_b = png.replace(".png", "_2.png")
        do_render(match_list[:mid], png,   title, subtitle + " (1/2)", is_results)
        do_render(match_list[mid:], png_b, title, subtitle + " (2/2)", is_results)
        save_cap(txt, png)
        cap_b = png_b.replace(".png", ".txt")
        open(cap_b, "w", encoding="utf-8").write(txt)
        print(f"→ {png_b}\n→ {cap_b}")
        return [png, png_b], cap_b

    if results:
        # Resultats: matchcenter.py, via les pàgines de Telegramm.
        scores = sources.week_scores([m.get("spielnummer", "") for m in ms])
        for m in ms:
            spielnr = m.get("spielnummer", "")
            if spielnr and spielnr in scores:
                m["score"]      = scores[spielnr]["score"]
                m["home_goals"] = scores[spielnr]["home_goals"]
                m["away_goals"] = scores[spielnr]["away_goals"]
            m["outcome"] = outcome(m)

        ms_results = [m for m in ms if not m.get("is_tournament")]

        # Guard: sense cap resultat no es genera ni es publica res.
        # Millor que el job peti a publicar una imatge plena de guionets.
        if not any(m.get("score") for m in ms_results):
            sys.exit("FATAL: cap resultat obtingut — no es genera cap imatge")

        txt = caption_results(ms_results)
        return maybe_split(ms_results, "RESULTATE", "UNSERE WOCHE", True, txt)

    elif len(real) == 1 and len(ms) == 1:
        m = dict(real[0])
        m["team_label"] = team_label(m)
        m["home_crest"] = None
        m["away_crest"] = None
        render.render_single_photo(m, png, photo_path=PITCH)
        if BLURRED_SIDES:
            add_blurred_sides(png)
        txt = caption_preview(ms)
        return save_cap(txt, png)

    else:
        txt = caption_preview(ms)
        return maybe_split(ms, "MATCH DAY", "SPIELE DER WOCHE", False, txt)


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
    ms = sources.load_matches()
    build(ms, anchor=anchor, results=(a.cmd == "results"),
          outdir=a.outdir, photo=a.photo, fetch_crests=not a.no_crests)
