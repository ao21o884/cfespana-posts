# -*- coding: utf-8 -*-
"""
C.F. España — Instagram post renderer (light edition).

  render_single(m)              -> editorial one-match poster
  render_list(ms)               -> weekly fixture table (venue as subline)
  render_list(ms, results=True) -> results table (category as subline)
"""
import os
import re
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
ASSETS = os.path.join(HERE, "assets")

W, H = 1080, 1350

# --- palette: warm paper, ink type, España red/yellow used sparingly -------
PAPER = (246, 244, 239)
CARDBG = (255, 255, 255)
INK = (24, 26, 32)
INK2 = (108, 112, 122)
INK3 = (176, 180, 190)
RED = (203, 32, 41)
RED_L = (250, 232, 232)
YELLOW = (243, 183, 20)
YELLOW_L = (253, 245, 218)
GREEN = (28, 148, 82)
GREEN_L = (226, 244, 233)
LINE = (226, 223, 216)


def anton(s):
    return ImageFont.truetype(os.path.join(FONTS, "Anton-Regular.ttf"), s)


def bc(s, w="Bold"):
    return ImageFont.truetype(os.path.join(FONTS, f"BarlowCondensed-{w}.ttf"), s)


def tw(d, t, f):
    b = d.textbbox((0, 0), t, font=f)
    return b[2] - b[0], b[3] - b[1]


def fit(d, t, fn, maxw, start, minsize=13):
    s = start
    while s > minsize:
        f = fn(s)
        if tw(d, t, f)[0] <= maxw:
            return f
        s -= 1
    return fn(minsize)


def background():
    """Warm paper with a soft red / yellow wash — present, not shouting."""
    base = Image.new("RGBA", (W, H), PAPER)
    wash = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(wash)
    d.ellipse([-380, -540, 640, 320], fill=(*RED, 44))
    d.ellipse([W - 540, H - 640, W + 440, H + 280], fill=(*YELLOW, 66))
    wash = wash.filter(ImageFilter.GaussianBlur(130))
    img = Image.alpha_composite(base, wash).convert("RGB")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 15], fill=RED)
    d.rectangle([0, 15, W, 23], fill=YELLOW)
    d.rectangle([0, H - 23, W, H - 15], fill=YELLOW)
    d.rectangle([0, H - 15, W, H], fill=RED)
    return img


def card(img, box, radius=20, fill=CARDBG, blur=9):
    """Rounded card with a soft drop shadow. Returns the same image object."""
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        [box[0] + 2, box[1] + 7, box[2] + 2, box[3] + 9], radius=radius, fill=(40, 36, 28, 52))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    merged = Image.alpha_composite(img.convert("RGBA"), sh).convert("RGB")
    img.paste(merged, (0, 0))
    ImageDraw.Draw(img).rounded_rectangle(box, radius=radius, fill=fill)
    return img


def load_crest(path, box):
    if not path or not os.path.exists(path):
        return None
    im = Image.open(path).convert("RGBA")
    r = min(box / im.width, box / im.height)
    return im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)


DAY_DE = {"Mo": "MONTAG", "Di": "DIENSTAG", "Mi": "MITTWOCH", "Do": "DONNERSTAG",
          "Fr": "FREITAG", "Sa": "SAMSTAG", "So": "SONNTAG"}
DAY_SHORT = {"Mo": "MO", "Di": "DI", "Mi": "MI", "Do": "DO", "Fr": "FR", "Sa": "SA", "So": "SO"}
MONTH = {1: "JANUAR", 2: "FEBRUAR", 3: "MÄRZ", 4: "APRIL", 5: "MAI", 6: "JUNI", 7: "JULI",
         8: "AUGUST", 9: "SEPTEMBER", 10: "OKTOBER", 11: "NOVEMBER", 12: "DEZEMBER"}


def short_venue(v):
    v = (v or "").strip()
    parts = [p.strip() for p in v.split(" - ") if p.strip()]
    if len(parts) >= 2:
        detail = parts[1]
        town = detail.split(",")[-1].strip()
        pitch = detail.split(",")[0].strip()
        return f"{pitch}, {town}" if town else pitch
    return v


def short_liga(c):
    c = (c or "")
    c = re.sub(r"^Cup\s+", "", c)
    c = c.replace("Meisterschaft ", "").replace(" - MFV", "")
    c = re.sub(r"\s{2,}", " ", c)
    c = re.sub(r"\s*-\s*(Herbstrunde|Frühjahrsrunde)", "", c)
    c = re.sub(r"\s*-\s*Gruppe\s*\d+", "", c)
    return c.strip().upper()


def es_split(txt):
    return [p for p in re.split(r"(C\.F\. España(?: / Italiana)?)", txt, flags=re.I) if p]


def is_es(part):
    return "ESPAÑA" in part.upper()


# =========================================================================
# LAYOUT A — one match
# =========================================================================
def render_single(m, out, **kw):
    img = background()
    d = ImageDraw.Draw(img)

    hc = load_crest(m.get("home_crest"), 92)
    ac = load_crest(m.get("away_crest"), 92)
    both = hc is not None and ac is not None   # all-or-nothing: both crests or none

    club = load_crest(os.path.join(ASSETS, "cfespana_big.png"), 132)
    if club:
        img.paste(club, (W - 100 - club.width, 60), club)
    d = ImageDraw.Draw(img)

    kick = short_liga(m["competition"])
    d.text((92, 72), kick, font=fit(d, kick, lambda s: bc(s, "Bold"), 600, 40, 20), fill=RED)
    d.text((92, 114), "SPIELTAG", font=anton(120), fill=INK)
    d.line([(92, 262), (W - 92, 262)], fill=LINE, width=3)

    # ---- date block + fixture
    top, bot = 300, 740
    card(img, [92, top, W - 92, bot], radius=24)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([92, top, 400, bot], radius=24, fill=RED)
    d.rectangle([344, top, 400, bot], fill=RED)

    dd, mm, yy = m["date"].split(".")
    dcx, dmid = 246, (top + bot) / 2
    d.text((dcx, dmid - 168), DAY_DE.get(m["dow"], m["dow"]), font=bc(42, "Bold"),
           fill=(255, 208, 208), anchor="mm")
    d.text((dcx, dmid - 26), dd, font=anton(190), fill=(255, 255, 255), anchor="mm")
    mon = MONTH.get(int(mm), mm)
    d.text((dcx, dmid + 120), mon,
           font=fit(d, mon, lambda s: bc(s, "Bold"), 240, 46, 20),
           fill=(255, 255, 255), anchor="mm")
    d.text((dcx, dmid + 174), yy, font=bc(36, "SemiBold"), fill=(255, 190, 190), anchor="mm")

    fx = 442
    fw = (W - 92) - fx - 40
    home_is_us = m["home"].upper().startswith("C.F. ESPAÑA")
    pill = "HEIMSPIEL" if home_is_us else "AUSWÄRTSSPIEL"
    pf = bc(32, "Bold")
    pw = tw(d, pill, pf)[0] + 44
    pill_top, pill_h = top + 40, 50
    d.rounded_rectangle([fx, pill_top, fx + pw, pill_top + pill_h], radius=pill_h // 2,
                        fill=YELLOW_L, outline=YELLOW, width=3)
    d.text((fx + pw / 2, pill_top + pill_h / 2), pill, font=pf, fill=(150, 106, 0), anchor="mm")

    rows = [(m["home"], hc), (m["away"], ac)]
    indent = 108 if both else 0
    nsize = 58
    while nsize > 22 and any(tw(d, n.upper(), anton(nsize))[0] > fw - indent for n, _ in rows):
        nsize -= 2
    nf = anton(nsize)

    # vertically centre [name / GEGEN / name] in the space under the pill
    span = pill_top + pill_h
    mid = (span + bot) / 2
    step = 108
    centres = (mid - step, mid + step)

    for i, ((nm, cr), cyy) in enumerate(zip(rows, centres)):
        if both and cr:
            img.paste(cr, (fx + (92 - cr.width) // 2, int(cyy - cr.height / 2)), cr)
            d = ImageDraw.Draw(img)
        x = fx + indent
        for part in es_split(nm.upper()):
            d.text((x, cyy), part, font=nf, fill=RED if is_es(part) else INK, anchor="lm")
            x += tw(d, part, nf)[0]

    # GEGEN sits exactly halfway between the two names
    gx = fx + indent
    d.line([(gx, mid), (gx + 54, mid)], fill=YELLOW, width=6)
    d.text((gx + 70, mid), "GEGEN", font=bc(34, "Bold"), fill=INK3, anchor="lm")

    # ---- kickoff + venue (content centred inside each card)
    iy, ih = 786, 186
    card(img, [92, iy, 480, iy + ih], radius=20, fill=INK)
    card(img, [502, iy, W - 92, iy + ih], radius=20)
    d = ImageDraw.Draw(img)

    kcx = (92 + 480) / 2
    d.text((kcx, iy + 40), "ANPFIFF", font=bc(32, "Bold"), fill=INK3, anchor="mm")
    tf, uf = anton(92), bc(38, "Bold")
    tW, uW = tw(d, m["time"], tf)[0], tw(d, "UHR", uf)[0]
    gapx = 16
    x0 = kcx - (tW + gapx + uW) / 2
    d.text((x0, iy + 116), m["time"], font=tf, fill=(255, 255, 255), anchor="lm")
    d.text((x0 + tW + gapx, iy + 132), "UHR", font=uf, fill=YELLOW, anchor="lm")

    vcx = (502 + W - 92) / 2
    ven = short_venue(m["venue"])
    v1, _, v2 = ven.partition(",")
    v1, v2 = v1.strip(), v2.strip().upper()
    d.text((vcx, iy + 40), "SPIELORT", font=bc(32, "Bold"), fill=INK2, anchor="mm")
    if v2:
        d.text((vcx, iy + 100), v1,
               font=fit(d, v1, lambda s: bc(s, "Bold"), 420, 52, 20), fill=INK, anchor="mm")
        d.text((vcx, iy + 148), v2,
               font=fit(d, v2, lambda s: bc(s, "SemiBold"), 420, 42, 18), fill=RED, anchor="mm")
    else:
        d.text((vcx, iy + 124), v1,
               font=fit(d, v1, lambda s: bc(s, "Bold"), 420, 52, 20), fill=INK, anchor="mm")

    d.text((W / 2, 1014), "KOMM VORBEI UND", font=anton(66), fill=INK, anchor="ma")
    d.text((W / 2, 1086), "UNTERSTÜTZE UNS!", font=anton(66), fill=RED, anchor="ma")

    footer(d)
    img.save(out, quality=95)
    return out


# =========================================================================
# LAYOUT B — several matches / results
# =========================================================================
def render_list(matches, out, title="SPIELPLAN", subtitle="SPIELE DER WOCHE",
                daterange="", results=False, **kw):
    img = background()
    club = load_crest(os.path.join(ASSETS, "cfespana_big.png"), 170)
    if club:
        img.paste(club, (W - 96 - club.width, 54), club)
    d = ImageDraw.Draw(img)

    tf = fit(d, title, anton, 560, 102, 50)
    d.text((92, 72), title, font=tf, fill=INK)
    by = 72 + tw(d, title, tf)[1] + 42
    sf = fit(d, subtitle, lambda s: bc(s, "Bold"), 520, 42, 20)
    d.rectangle([92, by, 92 + tw(d, subtitle, sf)[0] + 34, by + 54], fill=RED)
    d.text((109, by + 2), subtitle, font=sf, fill=(255, 255, 255))
    if daterange:
        d.text((92, by + 70), daterange, font=bc(40, "SemiBold"), fill=INK2)

    top, bottom = 328, H - 190
    n = max(1, len(matches))
    gap = 12
    rh = min(150, max(74, int((bottom - top) / n) - gap))
    y = top + max(0, ((bottom - top) - (n * rh + (n - 1) * gap)) // 2)

    C1, C2, C3 = 268, 776, W - 92
    MIDR = (C2 + C3) / 2

    fixes = [(m.get("label", "TURNIER").upper() if m.get("is_tournament")
              else f"{m['home']}  –  {m['away']}") for m in matches]
    fs = min(40, rh // 2 + 8)
    while fs > 15 and any(tw(d, t, bc(fs, "Bold"))[0] > C2 - C1 - 48 for t in fixes):
        fs -= 1
    FIXF = bc(fs, "Bold")

    subs = [(short_liga(m.get("competition", "")) if results else short_venue(m.get("venue", "")))
            for m in matches]
    ss = min(30, max(15, fs - 8))
    while ss > 13 and any(tw(d, t, bc(ss, "Medium"))[0] > C2 - C1 - 48 for t in subs):
        ss -= 1
    SUBF = bc(ss, "Medium")

    for i, m in enumerate(matches):
        ry = y + i * (rh + gap)
        tour = m.get("is_tournament")
        card(img, [92, ry, C3, ry + rh], radius=16, blur=7)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([92, ry, 114, ry + rh], radius=8, fill=RED if not tour else INK3)
        d.rectangle([102, ry, 114, ry + rh], fill=RED if not tour else INK3)

        wcx = (114 + C1) / 2
        if m.get("time"):
            d.text((wcx, ry + rh / 2 - 22), DAY_SHORT.get(m["dow"], m["dow"]),
                   font=bc(min(34, max(20, rh // 3)), "Bold"), fill=INK3, anchor="mm")
            d.text((wcx, ry + rh / 2 + 18), m["time"],
                   font=anton(min(46, max(24, rh // 2 - 6))), fill=INK, anchor="mm")
        else:
            d.text((wcx, ry + rh / 2 - 14), DAY_SHORT.get(m["dow"], m["dow"]),
                   font=anton(min(46, max(24, rh // 2 - 6))), fill=INK, anchor="mm")
            d.text((wcx, ry + rh / 2 + 24), "ZEIT OFFEN", font=bc(24, "SemiBold"),
                   fill=INK3, anchor="mm")
        d.line([(C1, ry + 14), (C1, ry + rh - 14)], fill=LINE, width=2)

        tx = C1 + 28
        fixture = fixes[i]
        fy = ry + rh / 2 - (19 if subs[i] else 0)
        if tour:
            d.text((tx, fy), fixture, font=FIXF, fill=INK2, anchor="lm")
        else:
            x = tx
            for part in es_split(fixture):
                d.text((x, fy), part, font=FIXF, fill=RED if is_es(part) else INK, anchor="lm")
                x += tw(d, part, FIXF)[0]
        if subs[i]:
            d.text((tx, ry + rh / 2 + 24), subs[i], font=SUBF, fill=INK3, anchor="lm")
        d.line([(C2, ry + 14), (C2, ry + rh - 14)], fill=LINE, width=2)

        if results:
            if tour or not m.get("score"):
                d.text((MIDR, ry + rh / 2), "–", font=bc(46, "Bold"), fill=INK3, anchor="mm")
            else:
                oc = m.get("outcome")
                bg = {"W": GREEN_L, "L": RED_L}.get(oc, (238, 236, 231))
                fg = {"W": GREEN, "L": RED}.get(oc, INK2)
                d.rounded_rectangle([MIDR - 88, ry + rh / 2 - 36, MIDR + 88, ry + rh / 2 + 36],
                                    radius=14, fill=bg)
                d.text((MIDR, ry + rh / 2), m["score"], font=anton(54), fill=fg, anchor="mm")
        else:
            lg = short_liga(m.get("competition", ""))
            d.text((MIDR, ry + rh / 2), lg,
                   font=fit(d, lg, lambda s: bc(s, "SemiBold"), C3 - C2 - 28, min(34, rh // 2), 14),
                   fill=INK2, anchor="mm")

    footer(ImageDraw.Draw(img))
    img.save(out, quality=95)
    return out


def footer(d):
    y = H - 166
    d.line([(92, y), (W - 92, y)], fill=LINE, width=3)
    t = "¡VAMOS ESPAÑA!"
    f = anton(46)
    w = d.textbbox((0, 0), t, font=f)[2]
    d.text((W / 2, y + 20), t, font=f, fill=INK, anchor="ma")
    d.line([(W / 2 - w / 2, y + 78), (W / 2, y + 78)], fill=RED, width=6)
    d.line([(W / 2, y + 78), (W / 2 + w / 2, y + 78)], fill=YELLOW, width=6)
    d.text((W / 2, y + 86), "@cfespanadeberna  ·  cfespana.ch", font=bc(28, "SemiBold"),
           fill=INK2, anchor="ma")
