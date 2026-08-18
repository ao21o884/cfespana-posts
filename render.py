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
    c = c.replace("Meisterschaft ", "").replace(" - MFV", "").replace(" / MFV", "")
    c = re.sub(r"\s{2,}", " ", c)
    c = re.sub(r"\s*-\s*(Herbstrunde|Frühjahrsrunde)", "", c)
    c = re.sub(r"\s*[-/]\s*Gruppe\s*\d+", "", c)
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
    d.text((92, 114), "MATCH DAY", font=anton(120), fill=INK)
    d.line([(92, 262), (W - 92, 262)], fill=LINE, width=3)

    # ---- date block + fixture
    top, bot = 300, 740
    card(img, [92, top, W - 92, bot], radius=24)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([92, top, 400, bot], radius=24, fill=RED)
    d.rectangle([344, top, 400, bot], fill=RED)

    dd, mm, yy = m["date"].split(".")
    dcx, dmid = 246, (top + bot) / 2
    d.text((dcx, dmid - 168), DAY_DE.get(m["dow"], m["dow"]), font=bc(38, "Bold"),
           fill=(255, 208, 208), anchor="mm")
    d.text((dcx, dmid - 20), dd, font=anton(160), fill=(255, 255, 255), anchor="mm")
    mon = MONTH.get(int(mm), mm)
    d.text((dcx, dmid + 108), mon,
           font=fit(d, mon, lambda s: bc(s, "Bold"), 240, 42, 18),
           fill=(255, 255, 255), anchor="mm")
    d.text((dcx, dmid + 158), yy, font=bc(34, "SemiBold"), fill=(255, 190, 190), anchor="mm")

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
    nsize = 62
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
    d.text((gx + 70, mid), "VS", font=bc(34, "Bold"), fill=INK3, anchor="lm")

    # ---- kickoff + venue (content centred inside each card)
    iy, ih = 786, 186
    card(img, [92, iy, 480, iy + ih], radius=20, fill=INK)
    card(img, [502, iy, W - 92, iy + ih], radius=20)
    d = ImageDraw.Draw(img)

    kcx = (92 + 480) / 2
    d.text((kcx, iy + 40), "ANPFIFF", font=bc(32, "Bold"), fill=INK3, anchor="mm")
    tf, uf = anton(86), bc(36, "Bold")
    tW, uW = tw(d, m["time"], tf)[0], tw(d, "UHR", uf)[0]
    gapx = 16
    x0 = kcx - (tW + gapx + uW) / 2
    d.text((x0, iy + 112), m["time"], font=tf, fill=(255, 255, 255), anchor="lm")
    d.text((x0 + tW + gapx, iy + 128), "UHR", font=uf, fill=YELLOW, anchor="lm")

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



PITCH = os.path.join(ASSETS, "pitch.jpg")

def _photo_bg(style="photo"):
    """Background: real photo with dark overlay (style='photo')
       or warm paper with red/yellow stripes (style='paper')."""
    from PIL import ImageFilter
    if style == "photo" and os.path.exists(PITCH):
        img = Image.open(PITCH).convert("RGB").resize((W, H), Image.LANCZOS)
        # dark gradient overlay so text reads clearly
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d  = ImageDraw.Draw(ov)
        # top: lighter; bottom: heavier
        for y in range(H):
            t = y / H
            a = int(140 + t * 100)   # 140 → 240 alpha — strong overlay
            d.line([(0, y), (W, y)], fill=(0, 0, 0, a))
        img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    else:
        img = background()   # warm paper fallback
    return img

def _draw_stripes(img):
    """Red top stripe + yellow accent, red bottom stripe + yellow accent."""
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 16], fill=RED)
    d.rectangle([0, 16, W, 26], fill=YELLOW)
    d.rectangle([0, H - 26, W, H - 16], fill=YELLOW)
    d.rectangle([0, H - 16, W, H], fill=RED)

def _info_row(d, m, y_centre, col_fill, label_fill, font_size=48):
    """Three equal columns: DATUM | ANPFIFF | SPIELORT."""
    dd, mm_s, yy = m["date"].split(".")
    day_label = DAY_DE.get(m["dow"], m["dow"])
    mon_label  = MONTH.get(int(mm_s), mm_s)
    ven = short_venue(m["venue"])
    v1, _, v2 = ven.partition(",")

    col_w = (W - 120) / 3
    cols  = [60 + col_w * i + col_w / 2 for i in range(3)]
    lf    = bc(24, "Bold")
    vf    = bc(font_size, "Bold")   # same size for all three

    # labels
    for cx, lbl in zip(cols, ["DATUM", "ANPFIFF", "SPIELORT"]):
        d.text((cx, y_centre - 52), lbl, font=lf, fill=label_fill, anchor="mm")

    # separators
    for i in [0, 1]:
        sx = cols[i] + col_w / 2
        d.line([(sx, y_centre - 38), (sx, y_centre + 52)], fill=label_fill, width=1)

    # date
    date_str = f"{day_label[:2]}  {dd}. {mon_label}"
    d.text((cols[0], y_centre + 8), date_str,
           font=fit(d, date_str, lambda s: bc(s, "Bold"), col_w - 24, font_size, 18),
           fill=col_fill, anchor="mm")
    d.text((cols[0], y_centre + 46), yy, font=bc(26, "SemiBold"), fill=label_fill, anchor="mm")

    # time
    d.text((cols[1], y_centre + 4), m["time"], font=vf, fill=col_fill, anchor="mm")
    d.text((cols[1], y_centre + 46), "UHR", font=bc(28, "Bold"), fill=YELLOW, anchor="mm")

    # venue
    v1s = v1.strip()
    d.text((cols[2], y_centre + 4), v1s,
           font=fit(d, v1s, lambda s: bc(s, "Bold"), col_w - 24, font_size, 18),
           fill=col_fill, anchor="mm")
    if v2.strip():
        d.text((cols[2], y_centre + 46), v2.strip().upper(),
               font=fit(d, v2.strip(), lambda s: bc(s, "SemiBold"), col_w - 24, 28, 14),
               fill=RED if col_fill != (255,255,255) else YELLOW, anchor="mm")


# =========================================================================
# LAYOUT C — one match, photo background (dark overlay)
# =========================================================================
def render_single_open(m, out, style="photo", **kw):
    img = _photo_bg(style)
    _draw_stripes(img)
    d   = ImageDraw.Draw(img)

    col_fill   = (255, 255, 255)
    label_fill = (180, 180, 180)

    # ── club crest top-left
    club = load_crest(os.path.join(ASSETS, "cfespana_big.png"), 110)
    if club:
        img.paste(club, (60, 38), club)
        d = ImageDraw.Draw(img)

    # ── MATCH DAY top right
    liga = short_liga(m["competition"])
    d.text((W - 60, 50), "MATCH DAY", font=anton(64), fill=(255,255,255), anchor="ra")
    d.text((W - 60, 116), liga,
           font=fit(d, liga, lambda s: bc(s, "Bold"), 500, 30, 14),
           fill=RED, anchor="ra")

    # ── HEIMSPIEL / AUSWÄRTSSPIEL pill
    home_is_us = m["home"].upper().startswith("C.F. ESPAÑA")
    pill = "HEIMSPIEL" if home_is_us else "AUSWÄRTSSPIEL"
    pf   = bc(28, "Bold")
    pw   = tw(d, pill, pf)[0] + 36
    d.rounded_rectangle([60, 174, 60 + pw, 174 + 42], radius=21,
                        fill=YELLOW_L, outline=YELLOW, width=2)
    d.text((60 + pw / 2, 195), pill, font=pf, fill=(130, 90, 0), anchor="mm")

    # ── separator
    d.line([(60, 236), (W - 60, 236)], fill=(255, 255, 255, 60), width=1)

    # ── teams — huge, centred on photo
    hc = load_crest(m.get("home_crest"), 90)
    ac = load_crest(m.get("away_crest"), 90)
    both = hc is not None and ac is not None

    def draw_team(name, crest, cy):
        indent = 110 if (both and crest) else 0
        nf = fit(d, name.upper(), anton, W - 120 - indent, 130, 30)
        if both and crest:
            img.paste(crest, (60, int(cy - crest.height / 2)), crest)
            d2 = ImageDraw.Draw(img)
        else:
            d2 = d
        x = 60 + indent
        for part in es_split(name.upper()):
            d2.text((x, cy), part, font=nf,
                    fill=RED if is_es(part) else (255, 255, 255), anchor="lm")
            x += tw(d2, part, nf)[0]

    draw_team(m["home"], hc, 460)
    # VS
    d.text((W / 2, 580), "VS", font=anton(80), fill=(255, 255, 255), anchor="mm")
    d.line([(60, 580), (W / 2 - 72, 580)], fill=(255, 255, 255, 40), width=1)
    d.line([(W / 2 + 72, 580), (W - 60, 580)], fill=(255, 255, 255, 40), width=1)
    draw_team(m["away"], ac, 700)

    # ── separator before info
    d.line([(60, 790), (W - 60, 790)], fill=(255, 255, 255, 60), width=1)

    # ── info row — equal font size
    _info_row(d, m, 920, col_fill=(255,255,255), label_fill=(170,170,170), font_size=46)

    # ── footer
    d.line([(60, H - 110), (W - 60, H - 110)], fill=(255, 255, 255, 40), width=1)
    d.text((W / 2, H - 74), "¡VAMOS ESPAÑA!", font=anton(52), fill=(255,255,255), anchor="mm")
    fw2 = d.textbbox((0, 0), "¡VAMOS ESPAÑA!", font=anton(52))[2]
    d.line([(W/2 - fw2//2, H - 34), (W/2, H - 34)], fill=RED, width=5)
    d.line([(W/2, H - 34), (W/2 + fw2//2, H - 34)], fill=YELLOW, width=5)

    img.save(out, quality=95)
    return out


# =========================================================================
# LAYOUT C2 — same as C but with warm paper background
# =========================================================================
def render_single_open_paper(m, out, **kw):
    return render_single_open(m, out, style="paper", **kw)


# =========================================================================
# LAYOUT D — multiple matches, photo background
# =========================================================================
def render_list_open(matches, out, title="MATCH DAY", subtitle="SPIELE DER WOCHE",
                     daterange="", results=False, style="photo", **kw):
    img = _photo_bg(style)
    _draw_stripes(img)

    club = load_crest(os.path.join(ASSETS, "cfespana_big.png"), 120)
    if club:
        img.paste(club, (60, 36), club)
    d = ImageDraw.Draw(img)

    col_text  = (255, 255, 255)
    col_muted = (170, 170, 170)

    # title
    tf = fit(d, title, anton, W - 64 - (club.width + 80 if club else 0), 110, 50)
    tx = 60 + (club.width + 20 if club else 0)
    d.text((tx, 48), title, font=tf, fill=col_text)
    ty = 48 + tw(d, title, tf)[1] + 8

    # subtitle pill
    sf  = bc(30, "Bold")
    spw = tw(d, subtitle, sf)[0] + 32
    d.rounded_rectangle([tx, ty, tx + spw, ty + 42], radius=21, fill=RED)
    d.text((tx + spw / 2, ty + 21), subtitle, font=sf, fill=(255,255,255), anchor="mm")
    if daterange:
        d.text((tx, ty + 52), daterange, font=bc(30, "SemiBold"), fill=col_muted)

    top    = ty + (96 if daterange else 60)
    bottom = H - 110
    n      = max(1, len(matches))
    rh     = min(148, max(72, int((bottom - top) / n) - 10))
    gap    = max(8, int((bottom - top - n * rh) / max(n - 1, 1)))
    C1, C2, C3 = 230, 760, W - 60

    for i, m in enumerate(matches):
        ry    = top + i * (rh + gap)
        tour  = m.get("is_tournament")
        mid_y = ry + rh / 2

        # semi-transparent row strip for readability
        row_ov = Image.new("RGBA", (W, H), (0,0,0,0))
        ImageDraw.Draw(row_ov).rounded_rectangle(
            [60, ry, W - 60, ry + rh], radius=12, fill=(0, 0, 0, 100))
        img = Image.alpha_composite(img.convert("RGBA"), row_ov).convert("RGB")
        d   = ImageDraw.Draw(img)

        # left accent bar
        d.rounded_rectangle([60, ry + 8, 66, ry + rh - 8], radius=3,
                            fill=RED if not tour else col_muted)

        # day + time col
        wcx = 60 + 90
        d.text((wcx, mid_y - 20), DAY_SHORT.get(m["dow"], m["dow"]),
               font=bc(min(30, max(18, rh // 3)), "Bold"), fill=col_muted, anchor="mm")
        if m.get("time"):
            d.text((wcx, mid_y + 20), m["time"],
                   font=anton(min(52, max(28, rh // 2))), fill=col_text, anchor="mm")
        else:
            d.text((wcx, mid_y + 18), "TBD", font=bc(26, "SemiBold"), fill=col_muted, anchor="mm")

        d.line([(60 + 172, ry + 14), (60 + 172, ry + rh - 14)], fill=(255,255,255,40), width=1)

        # fixture
        tx2  = 60 + 192
        fw2  = C2 - tx2 - 20
        fs   = min(42, rh // 2 + 8)
        fixture = (m.get("label", "TURNIER").upper() if tour
                   else f"{m['home']}  –  {m['away']}")
        while fs > 14 and tw(d, fixture, bc(fs, "Bold"))[0] > fw2:
            fs -= 1
        FIXF = bc(fs, "Bold")
        sub  = (short_liga(m.get("competition", "")) if results
                else short_venue(m.get("venue", "")))
        fy   = mid_y - (14 if sub else 0)
        if tour:
            d.text((tx2, fy), fixture, font=FIXF, fill=col_muted, anchor="lm")
        else:
            x = tx2
            for part in es_split(fixture):
                d.text((x, fy), part, font=FIXF,
                       fill=RED if is_es(part) else col_text, anchor="lm")
                x += tw(d, part, FIXF)[0]
        if sub:
            d.text((tx2, mid_y + 22), sub,
                   font=bc(max(14, fs - 10), "Medium"), fill=col_muted, anchor="lm")

        d.line([(C2, ry + 14), (C2, ry + rh - 14)], fill=(255,255,255,40), width=1)
        MIDR = (C2 + C3) / 2
        if results:
            if tour or not m.get("score"):
                d.text((MIDR, mid_y), "–", font=bc(46, "Bold"), fill=col_muted, anchor="mm")
            else:
                oc  = m.get("outcome")
                bg2 = {("W"): GREEN_L, ("L"): RED_L}.get(oc, (60, 60, 60))
                fg  = {("W"): GREEN, ("L"): RED}.get(oc, col_muted)
                d.rounded_rectangle([MIDR - 88, mid_y - 36, MIDR + 88, mid_y + 36],
                                    radius=14, fill=bg2)
                d.text((MIDR, mid_y), m["score"], font=anton(54), fill=fg, anchor="mm")
        else:
            lg = short_liga(m.get("competition", ""))
            d.text((MIDR, mid_y), lg,
                   font=fit(d, lg, lambda s: bc(s, "SemiBold"), C3 - C2 - 28, min(34, rh//2), 14),
                   fill=col_muted, anchor="mm")

    # footer
    d.line([(60, H - 98), (W - 60, H - 98)], fill=(255,255,255,40), width=1)
    d.text((W / 2, H - 68), "¡VAMOS ESPAÑA!", font=anton(46), fill=(255,255,255), anchor="mm")
    fw3 = d.textbbox((0, 0), "¡VAMOS ESPAÑA!", font=anton(46))[2]
    d.line([(W/2 - fw3//2, H - 30), (W/2, H - 30)], fill=RED,    width=5)
    d.line([(W/2,          H - 30), (W/2 + fw3//2, H - 30)], fill=YELLOW, width=5)

    img.save(out, quality=95)
    return out


# =========================================================================
# LAYOUT D2 — multiple matches, paper background
# =========================================================================
def render_list_open_paper(matches, out, **kw):
    return render_list_open(matches, out, style="paper", **kw)
# -*- coding: utf-8 -*-
"""
New render functions — photo-background style (V3 final).
Drop-in replacements for render_single and render_list.
"""

def _photo_overlay(raw_img, top_alpha=40, bot_alpha=150):
    from PIL import Image, ImageDraw
    W, H = raw_img.size
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d  = ImageDraw.Draw(ov)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(0, 0, 0, int(top_alpha + t * (bot_alpha - top_alpha))))
    return Image.alpha_composite(raw_img.convert("RGBA"), ov).convert("RGB")


def _stripes(img, RED, YELLOW):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    W, H = img.size
    d.rectangle([0, 0, W, 16],      fill=RED);    d.rectangle([0, 16, W, 26],    fill=YELLOW)
    d.rectangle([0, H-26, W, H-16], fill=YELLOW); d.rectangle([0, H-16, W, H],   fill=RED)



# shared venue formatter
def fmt_venue(v):
    """
    ICS:  'Weissenstein, Bern - Fussballfeld Weissenstein 3' → 'Weissenstein, Bern'
    ICS:  'Pöschen, Schwarzenburg - Hauptplatz'              → 'Pöschen, Schwarzenburg'
    Web:  'Weissenstein - Fussballfeld Weissenstein 3, Bern' → 'Weissenstein, Bern'
    Web:  'Pöschen - Hauptplatz, Schwarzenburg'              → 'Pöschen, Schwarzenburg'
    """
    v = (v or "").strip()
    if not v:
        return v
    # ICS format: "Place, City - Fieldname"  → keep "Place, City"
    if " - " in v:
        before_dash = v.split(" - ")[0].strip()
        if "," in before_dash:
            return before_dash          # "Weissenstein, Bern"
        # Web format: "Place - Fieldname, City" → "Place, City"
        city = v.rsplit(",", 1)[-1].strip() if "," in v else ""
        return f"{before_dash}, {city}" if city else before_dash
    if "," in v:
        parts = v.split(",")
        return f"{parts[0].strip()}, {parts[-1].strip()}"
    return v


# shared footer — no horizontal lines, well spaced from bottom
#   stripe:    H-26
#   @sub:      H-44
#   underline: H-60
#   ¡VAMOS!:   H-96
#   UNTERSÜTZ: H-172
#   KOMM:      H-222

def _footer_photo(d, img, W, H, RED, YELLOW, INK2, bc, anton):
    SUB_CY   = H - 44
    UNDERL   = H - 60
    VAMOS_CY = H - 96
    KOMM2_CY = H - 172
    KOMM1_CY = H - 222

    d.text((W//2, KOMM1_CY), "KOMM VORBEI UND",  font=anton(46), fill=(255,255,255), anchor="mm")
    d.text((W//2, KOMM2_CY), "UNTERSTÜTZE UNS!", font=anton(46), fill=RED,           anchor="mm")
    d.text((W//2, VAMOS_CY), "¡VAMOS ESPAÑA!",   font=anton(48), fill=(255,255,255), anchor="mm")
    fw = d.textbbox((0,0), "¡VAMOS ESPAÑA!", font=anton(48))[2]
    d.line([(W//2-fw//2, UNDERL), (W//2,       UNDERL)], fill=RED,    width=5)
    d.line([(W//2,       UNDERL), (W//2+fw//2, UNDERL)], fill=YELLOW, width=5)
    d.text((W//2, SUB_CY), "@cfespanadeberna  ·  cfespana.ch",
           font=bc(26, "SemiBold"), fill=(200,200,200), anchor="mm")

FOOTER_RESERVE = 222 + 36   # KOMM1_CY offset from bottom + top gap = 258


def render_single_photo(m, out, photo_path, **kw):
    """Single-match post on photo background — V3 final design."""
    import re
    from PIL import Image, ImageDraw

    W2, H2 = W, H
    raw = Image.open(photo_path).convert("RGB").resize((W2, H2), Image.LANCZOS)
    img = _photo_overlay(raw, top_alpha=40, bot_alpha=150)
    _stripes(img, RED, YELLOW)
    d = ImageDraw.Draw(img)

    # ONE crest top-right
    club = load_crest(os.path.join(ASSETS, "cfespana_big.png"), 110)
    CREST_Y = 32
    if club:
        img.paste(club, (W2 - 52 - club.width, CREST_Y), club)
        d = ImageDraw.Draw(img)
    CREST_BOT = CREST_Y + (club.height if club else 110)

    # Liga + team label top-left — bigger font
    liga_str   = short_liga(m.get("competition", ""))
    team_label = m.get("team_label", "1. Mannschaft")
    d.text((52, 44), liga_str,
           font=fit(d, liga_str, lambda s: bc(s, "Bold"), W2//2 - 60, 38, 16),
           fill=RED, anchor="lm")
    d.text((52, 88), team_label, font=bc(32, "Bold"), fill=(200, 200, 200), anchor="lm")

    # MATCH DAY — no separator line
    MD_Y   = CREST_BOT + 20
    md_fnt = anton(120)
    md_bb  = d.textbbox((92, MD_Y), "MATCH DAY", font=md_fnt)
    MD_BOT = md_bb[3]
    d.text((92, MD_Y), "MATCH DAY", font=md_fnt, fill=(255, 255, 255))

    # Cards start right after MATCH DAY
    CARD_TOP = MD_BOT + 20
    CARD_H   = 460
    CARD_BOT = CARD_TOP + CARD_H

    # Red date block
    d.rounded_rectangle([92, CARD_TOP, 440, CARD_BOT], radius=18, fill=RED)
    dd2, mm_s2, yy2 = m["date"].split(".")
    day_l2 = DAY_DE.get(m["dow"], m["dow"])
    mon_l2 = MONTH.get(int(mm_s2), mm_s2)
    dcx  = (92 + 440) // 2
    dmid = CARD_TOP + CARD_H // 2
    d.text((dcx, dmid-155), day_l2,  font=bc(40, "Bold"),  fill=(255,208,208), anchor="mm")
    d.text((dcx, dmid-18),  dd2,     font=anton(175),       fill=(255,255,255), anchor="mm")
    d.text((dcx, dmid+108), mon_l2,
           font=fit(d, mon_l2, lambda s: bc(s, "Bold"), 240, 42, 18),
           fill=(255, 255, 255), anchor="mm")
    d.text((dcx, dmid+158), yy2, font=bc(34, "SemiBold"), fill=(255,190,190), anchor="mm")

    # White team card
    TL, TR = 462, W2-92
    d.rounded_rectangle([TL, CARD_TOP, TR, CARD_BOT], radius=18,
                        fill=(255,255,255), outline=(230,230,230), width=1)

    # Pill
    home_is_us = m["home"].upper().startswith("C.F. ESPAÑA")
    pill = "HEIMSPIEL" if home_is_us else "AUSWÄRTSSPIEL"
    pf   = bc(30, "Bold"); pw = tw(d, pill, pf)[0] + 40
    PX = TL + 20; PT = CARD_TOP + 26; PH = 44
    d.rounded_rectangle([PX, PT, PX+pw, PT+PH], radius=22, fill=YELLOW_L, outline=YELLOW, width=3)
    d.text((PX + pw//2, PT + PH//2), pill, font=pf, fill=(150, 106, 0), anchor="mm")

    # Teams — equal spacing
    TX = TL + 20; FW2 = TR - TX - 20
    nsize = 64
    while nsize > 22 and (tw(d, m["home"].upper(), anton(nsize))[0] > FW2 or
                           tw(d, m["away"].upper(), anton(nsize))[0] > FW2):
        nsize -= 2
    nf = anton(nsize)
    home_bb = d.textbbox((0,0), m["home"].upper(), font=nf)
    away_bb = d.textbbox((0,0), m["away"].upper(), font=nf)
    vs_bb   = d.textbbox((0,0), "vs", font=bc(30, "Bold"))
    home_h  = home_bb[3]-home_bb[1]; away_h = away_bb[3]-away_bb[1]; vs_h = vs_bb[3]-vs_bb[1]
    ZONE_TOP = PT+PH+12; ZONE_BOT = CARD_BOT-20
    zone_h   = ZONE_BOT-ZONE_TOP; total_h = home_h+vs_h+away_h; gap = (zone_h-total_h)//4
    home_y = ZONE_TOP+gap; vs_y = home_y+home_h+gap; away_y = vs_y+vs_h+gap
    d.text((TX, home_y), m["home"].upper(), font=nf, fill=RED if home_is_us else INK, anchor="lt")
    d.text((TX, vs_y),   "vs", font=bc(30, "Bold"), fill=INK3, anchor="lt")
    d.text((TX, away_y), m["away"].upper(), font=nf, fill=INK if home_is_us else RED, anchor="lt")

    # ANPFIFF + SPIELORT
    IY = CARD_BOT + 20; IH = 210
    d.rounded_rectangle([92, IY, 480, IY+IH], radius=18, fill=INK)
    kcx = (92+480)//2
    d.text((kcx, IY+34), "ANPFIFF", font=bc(30, "Bold"), fill=INK3, anchor="mm")
    tf, uf = anton(88), bc(36, "Bold")
    tW2b   = tw(d, m["time"], tf)[0]; uW = tw(d, "UHR", uf)[0]
    x0 = kcx - (tW2b + 14 + uW) // 2
    d.text((x0,        IY+108), m["time"], font=tf, fill=(255,255,255), anchor="lm")
    d.text((x0+tW2b+14,IY+122), "UHR",    font=uf, fill=YELLOW,        anchor="lm")

    d.rounded_rectangle([500, IY, W2-92, IY+IH], radius=18,
                        fill=(255,255,255), outline=(230,230,230), width=1)
    ven2 = fmt_venue(m.get("venue", "")); v1_2, _, v2_2 = ven2.partition(",")
    vcx2 = (500 + W2-92)//2
    d.text((vcx2, IY+34),  "SPIELORT", font=bc(30, "Bold"), fill=INK2, anchor="mm")
    d.text((vcx2, IY+108), v1_2.strip(),
           font=fit(d, v1_2.strip(), lambda s: bc(s, "Bold"), (W2-92-500)-30, 50, 18),
           fill=INK, anchor="mm")
    if v2_2.strip():
        d.text((vcx2, IY+162), v2_2.strip().upper(),
               font=fit(d, v2_2.strip(), lambda s: bc(s, "SemiBold"), (W2-92-500)-30, 30, 13),
               fill=RED, anchor="mm")

    _footer_photo(d, img, W2, H2, RED, YELLOW, INK2, bc, anton)
    img.save(out, quality=95)
    return out


DAY_SHORT_MAP = {"Mo":"MO","Di":"DI","Mi":"MI","Do":"DO","Fr":"FR","Sa":"SA","So":"SO"}


def _is_tournament_row(m):
    return "Turnier" in (m.get("competition","") or "") or m.get("is_tournament", False)


def _is_senior_row(m):
    c = m.get("competition","")
    return ("Senioren" in c or "Senior" in c) and not _is_tournament_row(m)


def _junior_label(competition, label=""):
    import re
    # First try the label field (e.g. "Turnier Jun.E")
    src = label or competition or ""
    mt = re.search(r'Jun(?:ioren)?[\.\s]*([A-G])', src, re.I)
    return f"Jun. {mt.group(1).upper()}" if mt else ""


def render_list_photo(matches, out, photo_path, title="MATCH DAY",
                      subtitle="SPIELE DER WOCHE", daterange="",
                      results=False, **kw):
    """Multi-match post on photo background."""
    import re
    from PIL import Image, ImageDraw

    W2, H2 = W, H
    raw = Image.open(photo_path).convert("RGB").resize((W2, H2), Image.LANCZOS)
    img = _photo_overlay(raw, top_alpha=40, bot_alpha=160)
    _stripes(img, RED, YELLOW)
    d = ImageDraw.Draw(img)

    # ONE crest top-right
    club = load_crest(os.path.join(ASSETS, "cfespana_big.png"), 110)
    CREST_Y = 32
    if club:
        img.paste(club, (W2 - 52 - club.width, CREST_Y), club)
        d = ImageDraw.Draw(img)
    CREST_BOT = CREST_Y + (club.height if club else 110)

    # Subtitle + daterange top-left — bigger font
    d.text((52, 44), subtitle,
           font=fit(d, subtitle, lambda s: bc(s, "Bold"), W2//2 - 60, 38, 16),
           fill=RED, anchor="lm")
    if daterange:
        d.text((52, 88), daterange, font=bc(28, "Bold"), fill=(200,200,200), anchor="lm")

    # MATCH DAY / RESULTATE — no separator line
    MD_Y   = CREST_BOT + 20
    md_fnt = anton(120)
    md_bb  = d.textbbox((92, MD_Y), title, font=md_fnt)
    MD_BOT = md_bb[3]
    d.text((92, MD_Y), title, font=md_fnt, fill=(255, 255, 255))

    ROWS_TOP    = MD_BOT + 20
    FOOTER_TOP  = H2 - FOOTER_RESERVE   # rows must end before footer

    n            = max(1, len(matches))
    gap2         = 8
    # Start with equal base height for all rows
    avail        = FOOTER_TOP - ROWS_TOP - gap2*(n-1)
    base_h       = max(72, avail // n)

    # Pre-calculate which rows need extra height (text too long for single line)
    RIGHT_W = 200
    DIVX    = 256
    FX_test = DIVX + 14
    FEND_test = W2 - 72 - RIGHT_W

    def needs_two_lines(m):
        """True if fixture text won't fit on one line at a readable font size (min 24px)."""
        if _is_tournament_row(m):
            return False
        home = m.get("home",""); away = m.get("away","")
        fixture = f"{home}  –  {away}"
        tmp = Image.new("RGB",(W2,H2)); tmp_d = ImageDraw.Draw(tmp)
        # min readable font = 24px; if it doesn't fit at that size, use two lines
        return tw(tmp_d, fixture, bc(24,"Bold"))[0] > FEND_test - FX_test - 10

    EXTRA = 35   # extra px for rows that need two lines
    n_extra = sum(1 for m in matches if needs_two_lines(m))
    if n_extra > 0:
        avail2 = FOOTER_TOP - ROWS_TOP - gap2*(n-1) - EXTRA*n_extra
        base_h = max(72, avail2 // n)
    tall_h = base_h + EXTRA
    RIGHT_W      = 200
    DIVX         = 256

    for i, m in enumerate(matches):
        row_h = tall_h if needs_two_lines(m) else base_h
        ry    = ROWS_TOP + sum(
            (tall_h if needs_two_lines(matches[j]) else base_h) + gap2
            for j in range(i))
        mid   = ry + row_h // 2
        tour  = _is_tournament_row(m)

        # Semi-transparent white card
        row_ov = Image.new("RGBA", (W2, H2), (0,0,0,0))
        ImageDraw.Draw(row_ov).rounded_rectangle(
            [72, ry, W2-72, ry+row_h], radius=14, fill=(255,255,255,210))
        img = Image.alpha_composite(img.convert("RGBA"), row_ov).convert("RGB")
        d   = ImageDraw.Draw(img)

        # Left accent bar
        d.rounded_rectangle([72, ry+8, 78, ry+row_h-8], radius=3,
                            fill=RED if not tour else INK3)

        # Day + time — generous vertical gap between them
        d.text((160, mid-22), DAY_SHORT_MAP.get(m.get("dow",""), ""),
               font=bc(30, "Bold"), fill=INK3, anchor="mm")
        d.text((160, mid+20), m.get("time","") or "--:--",
               font=anton(min(44, max(24, row_h//2))), fill=INK, anchor="mm")

        # Centre divider
        d.line([(DIVX, ry+12), (DIVX, ry+row_h-12)], fill=LINE, width=2)

        FX   = DIVX + 14
        FEND = W2 - 72 - RIGHT_W

        if tour:
            line1   = "Turnier Junior*innen E-F-G"
            venue_s = fmt_venue(m.get("venue",""))
            fs = 30
            while fs > 12 and tw(d, line1, bc(fs,"Bold"))[0] > FEND-FX-10:
                fs -= 1
            fy = mid - (14 if venue_s else 0)
            d.text((FX, fy), line1, font=bc(fs,"Bold"), fill=INK2, anchor="lm")
            if venue_s:
                d.text((FX, mid+18), venue_s, font=bc(max(12,fs-10),"Medium"), fill=INK2, anchor="lm")

        elif needs_two_lines(m):
            home    = m.get("home",""); away = m.get("away","")
            venue_s = fmt_venue(m.get("venue",""))
            # Fit each team name independently
            fs2 = 28
            while fs2 > 14 and (tw(d, home, bc(fs2,"Bold"))[0] > FEND-FX-10 or
                                  tw(d, away, bc(fs2,"Bold"))[0] > FEND-FX-10):
                fs2 -= 1
            FF2 = bc(fs2,"Bold")
            lh  = int(fs2 * 1.35)          # line height
            venue_fs = 15                   # fixed readable venue size
            venue_lh = int(venue_fs * 1.4)

            total_h = lh * 2 + (venue_lh if venue_s else 0)
            ly = mid - total_h // 2

            def draw_tline(text, y):
                x = FX
                for part in re.split(r'(C\.F\. España(?:\s*/\s*Italiana)?)', text):
                    col = RED if is_es(part) else INK
                    d.text((x, y), part, font=FF2, fill=col, anchor="lm")
                    x += tw(d, part, FF2)[0]

            draw_tline(home, ly)
            draw_tline(away, ly + lh)
            if venue_s:
                d.text((FX, ly + lh*2 + 4), venue_s,
                       font=bc(venue_fs, "Medium"), fill=INK2, anchor="lm")

        else:
            home    = m.get("home",""); away = m.get("away","")
            venue_s = fmt_venue(m.get("venue",""))
            fixture = f"{home}  –  {away}"
            fs = min(32, row_h//2+2)
            while fs > 12 and tw(d, fixture, bc(fs,"Bold"))[0] > FEND-FX-10:
                fs -= 1
            FF = bc(fs,"Bold")
            fy = mid - (14 if venue_s else 0)
            x  = FX
            for part in re.split(r'(C\.F\. España(?:\s*/\s*Italiana)?)', fixture):
                col = RED if is_es(part) else INK
                d.text((x, fy), part, font=FF, fill=col, anchor="lm")
                x += tw(d, part, FF)[0]
            if venue_s:
                d.text((FX, mid+18), venue_s, font=bc(max(12,fs-10),"Medium"), fill=INK2, anchor="lm")

        # Right column
        d.line([(W2-72-RIGHT_W, ry+12), (W2-72-RIGHT_W, ry+row_h-12)], fill=LINE, width=2)
        RCX = W2 - 72 - RIGHT_W//2

        if tour:
            jl = _junior_label(m.get("competition",""), m.get("label",""))
            rl = jl if jl else "TURNIER"
            d.text((RCX, mid), rl,
                   font=fit(d, rl, lambda s: bc(s,"SemiBold"), RIGHT_W-20, 28, 12),
                   fill=INK2, anchor="mm")
        elif needs_two_lines(m):
            if results:
                score = m.get("score","")
                liga  = short_liga(m.get("competition",""))
                if score:
                    LIGA_FS = 24
                    # Check if liga fits in one line
                    if tw(d, liga, bc(LIGA_FS,"SemiBold"))[0] > RIGHT_W-12:
                        # Two lines for category
                        words = liga.split(); mid_w = max(1, len(words)//2)
                        la = " ".join(words[:mid_w]); lb = " ".join(words[mid_w:])
                        fs_r = LIGA_FS
                        while fs_r > 12 and (tw(d,la,bc(fs_r,"SemiBold"))[0] > RIGHT_W-12 or
                                             tw(d,lb,bc(fs_r,"SemiBold"))[0] > RIGHT_W-12):
                            fs_r -= 1
                        lh = int(fs_r * 1.3)
                        d.text((RCX, mid-40-lh//2), la, font=bc(fs_r,"SemiBold"), fill=INK2, anchor="mm")
                        d.text((RCX, mid-40+lh//2), lb, font=bc(fs_r,"SemiBold"), fill=INK2, anchor="mm")
                    else:
                        d.text((RCX, mid-36), liga, font=bc(LIGA_FS,"SemiBold"), fill=INK2, anchor="mm")
                    d.text((RCX, mid+22), score, font=anton(min(46,row_h//2)), fill=INK, anchor="mm")
                else:
                    d.text((RCX, mid-14), liga, font=bc(13,"SemiBold"), fill=INK2, anchor="mm")
                    d.text((RCX, mid+12), "–",  font=bc(34,"Bold"),     fill=INK3, anchor="mm")
            else:
                comp  = short_liga(m.get("competition",""))
                words = comp.split(); mid_w = max(1, len(words)//2)
                la = " ".join(words[:mid_w]); lb = " ".join(words[mid_w:])
                fs_r = 18
                while fs_r > 10 and (tw(d,la,bc(fs_r,"SemiBold"))[0] > RIGHT_W-16 or
                                      tw(d,lb,bc(fs_r,"SemiBold"))[0] > RIGHT_W-16):
                    fs_r -= 1
                d.text((RCX, mid-int(fs_r*0.8)), la, font=bc(fs_r,"SemiBold"), fill=INK2, anchor="mm")
                d.text((RCX, mid+int(fs_r*0.8)), lb, font=bc(fs_r,"SemiBold"), fill=INK2, anchor="mm")
        else:
            if results:
                score = m.get("score","")
                liga  = short_liga(m.get("competition",""))
                if score:
                    LIGA_FS = 24
                    if tw(d, liga, bc(LIGA_FS,"SemiBold"))[0] > RIGHT_W-12:
                        words = liga.split(); mid_w = max(1, len(words)//2)
                        la = " ".join(words[:mid_w]); lb = " ".join(words[mid_w:])
                        fs_r = LIGA_FS
                        while fs_r > 12 and (tw(d,la,bc(fs_r,"SemiBold"))[0] > RIGHT_W-12 or
                                             tw(d,lb,bc(fs_r,"SemiBold"))[0] > RIGHT_W-12):
                            fs_r -= 1
                        lh = int(fs_r * 1.3)
                        d.text((RCX, mid-40-lh//2), la, font=bc(fs_r,"SemiBold"), fill=INK2, anchor="mm")
                        d.text((RCX, mid-40+lh//2), lb, font=bc(fs_r,"SemiBold"), fill=INK2, anchor="mm")
                    else:
                        d.text((RCX, mid-36), liga, font=bc(LIGA_FS,"SemiBold"), fill=INK2, anchor="mm")
                    d.text((RCX, mid+22), score, font=anton(44), fill=INK, anchor="mm")
                else:
                    d.text((RCX, mid-14), liga, font=bc(13,"SemiBold"), fill=INK2, anchor="mm")
                    d.text((RCX, mid+12), "–",  font=bc(34,"Bold"),     fill=INK3, anchor="mm")
            else:
                rl = short_liga(m.get("competition",""))
                d.text((RCX, mid), rl,
                       font=fit(d, rl, lambda s: bc(s,"SemiBold"), RIGHT_W-20, 28, 12),
                       fill=INK2, anchor="mm")

    if not results:
        pass  # Komm vorbei only for preview — already in footer
    _footer_photo(d, img, W2, H2, RED, YELLOW, INK2, bc, anton)

    img.save(out, quality=95)
    return out
