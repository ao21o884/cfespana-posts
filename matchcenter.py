# -*- coding: utf-8 -*-
"""
Capa de xarxa del matchcenter FVBJ/AFBJ per a C.F. España.

Tres feines:
  1. Sessió HTTP amb capçaleres de navegador (evita el 403).
  2. Calendari EN VIU des del Vereinsspielplan (a=vs) -> cache/spielplan.json
  3. Resultats des de les actes de partit / Spieltelegramm (?tg=...)

Per què les actes: 'Aktuelle Spiele' només llista partits d'avui endavant i
'Resultate + Ranglisten' només l'última jornada. L'acta d'un partit té un ID
permanent i no desapareix mai. Per això anem apuntant els IDs a
cache/tg_map.json cada execució i després els consultem quan calgui.

CLI:
    python matchcenter.py                # prova-ho tot
    python matchcenter.py calendar       # refresca el calendari
    python matchcenter.py scores         # marcadors dels partits coneguts
    python matchcenter.py dump           # desa l'HTML cru a debug/
"""
import os, re, sys, json, time
import datetime as dt

import requests
from bs4 import BeautifulSoup

# curl_cffi imita l'empremta TLS de Chrome. El WAF del matchcenter bloqueja
# les connexions de python-requests per la seva empremta TLS, abans i tot de
# mirar les capçaleres. Si no està instal·lat, caiem a requests (i molt
# probablement rebrem 403).
try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

HERE      = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "cache")
TG_MAP    = os.path.join(CACHE_DIR, "tg_map.json")
SPIELPLAN = os.path.join(CACHE_DIR, "spielplan.json")

BASE = "https://matchcenter.fvbj-afbj.ch/default.aspx"
CLUB = {"v": "1368", "oid": "6", "lng": "1"}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36")

DOW = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

# Si el Vereinsspielplan retorna menys partits que això, no ens en fiem
# i conservem el calendari anterior.
MIN_PLAUSIBLE = 15

US = "C.F. España"

_session = None


# ------------------------------------------------------------------ xarxa

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-CH,de;q=0.9,fr;q=0.8,en;q=0.7",
    "Upgrade-Insecure-Requests": "1",
}


def session():
    """Sessió reutilitzable, escalfada amb una visita a la portada del club."""
    global _session
    if _session is not None:
        return _session

    if cffi_requests is not None:
        s = cffi_requests.Session(impersonate="chrome")
        print("  · client: curl_cffi (TLS de Chrome)")
    else:
        s = requests.Session()
        print("  ! curl_cffi no instal·lat — provant amb requests "
              "(el matchcenter segurament retornarà 403)")

    s.headers.update(HEADERS)
    r = s.get(BASE, params=CLUB, timeout=25)
    r.raise_for_status()
    _session = s
    return s


def fetch(params, tries=3):
    """GET amb Referer i reintents amb espera creixent."""
    s = session()
    referer = f"{BASE}?v={CLUB['v']}&oid={CLUB['oid']}&lng={CLUB['lng']}"
    last = None
    for n in range(tries):
        try:
            r = s.get(BASE, params={**CLUB, **params},
                      headers={"Referer": referer}, timeout=25)
            r.raise_for_status()
            return r.text
        except Exception as e:
            last = e
            time.sleep(2 * (n + 1))
    raise last


def _text_lines(html):
    soup = BeautifulSoup(html, "html.parser")
    return [l.strip() for l in soup.get_text("\n").splitlines() if l.strip()]


# -------------------------------------------------------------- calendari

_DATE_RE = re.compile(r'^(Mo|Di|Mi|Do|Fr|Sa|So)\s+(\d{2})\.(\d{2})\.(\d{4})$')
_TIME_RE = re.compile(r'^(\d{1,2}):(\d{2})$')
_COMP_RE = re.compile(r'(Meisterschaft|Berner Cup|Cup|Turnier|Liga|Gruppe)', re.I)
_SPNR_RE = re.compile(r'Spielnummer\s*:?\s*(\d+)')
_JUN_RE  = re.compile(r'Jun\.?\s*([A-G])\b', re.I)


def _block_to_match(date_obj, time_val, lines):
    """Converteix un bloc de línies en un dict de partit, o None."""
    body = " \n ".join(lines)
    is_tour = any(l.startswith("Turnier") for l in lines[:2])

    sm = _SPNR_RE.search(body)
    spielnummer = sm.group(1) if sm else ""

    if not is_tour and not spielnummer:
        return None                       # bloc de soroll

    date_str = date_obj.strftime("%d.%m.%Y")
    dow      = DOW[date_obj.weekday()]

    if is_tour:
        jm    = _JUN_RE.search(body)
        label = f"Turnier Jun.{jm.group(1).upper()}" if jm else "Turnier"
        home, away, competition = US, "", "Turnier"
    else:
        label = ""
        # Els equips van abans de la línia de competició: A / "-" / B
        head = []
        for l in lines:
            if _COMP_RE.search(l) and not l.startswith("Turnier"):
                break
            head.append(l)
        home = away = ""
        if "-" in head:
            i = head.index("-")
            if i > 0:
                home = head[i - 1]
            if i + 1 < len(head):
                away = head[i + 1]
        elif len(head) >= 2:
            home, away = head[0], head[1]
        if not home:
            return None
        competition = ""
        for l in lines:
            if _COMP_RE.search(l) and not _SPNR_RE.search(l):
                competition = re.sub(r'\s+', ' ', l).strip()
                break

    # El recinte és l'última línia del bloc, després del Spielnummer
    venue = ""
    for l in reversed(lines):
        if _SPNR_RE.search(l) or _COMP_RE.search(l):
            break
        if l.startswith("Organisator"):
            continue
        venue = l
        break

    return {
        "dow": dow, "date": date_str, "time": time_val,
        "home": home, "away": away,
        "competition": competition, "label": label,
        "venue": venue, "is_tournament": is_tour,
        "spielnummer": spielnummer,
        "score": None, "home_v": None, "away_v": None,
        "uid": spielnummer or f"{date_str}_{time_val}_{home[:6]}",
    }


def parse_spielplan(html):
    """Parseja el Vereinsspielplan (a=vs) i retorna la llista de partits."""
    lines = _text_lines(html)

    # Salta el menú de navegació: comença a la primera capçalera de data
    start = 0
    for i, l in enumerate(lines):
        if _DATE_RE.match(l):
            start = i
            break
    lines = lines[start:]

    matches   = []
    state = {"date": None, "time": "", "lines": None}

    def flush():
        if state["date"] and state["lines"]:
            m = _block_to_match(state["date"], state["time"], state["lines"])
            if m:
                matches.append(m)
        state["lines"] = None
        state["time"]  = ""

    for l in lines:
        dm = _DATE_RE.match(l)
        if dm:
            flush()
            try:
                state["date"] = dt.date(int(dm.group(4)), int(dm.group(3)), int(dm.group(2)))
            except ValueError:
                state["date"] = None
            continue

        if state["date"] is None:
            continue

        tm = _TIME_RE.match(l)
        if tm:
            flush()
            state["time"]  = f"{int(tm.group(1)):02d}:{tm.group(2)}"
            state["lines"] = []
            continue

        if state["lines"] is None:
            state["lines"] = []          # partit sense hora indicada
        state["lines"].append(l)

    flush()
    matches.sort(key=lambda m: (m["date"].split(".")[::-1], m["time"]))
    return matches


def match_key(m):
    """Clau estable d'un partit, per fusionar sense duplicar."""
    nr = (m.get("spielnummer") or "").strip()
    if nr:
        return nr
    return f"{m.get('date','')}_{m.get('time','')}_{(m.get('home') or '')[:12]}"


def merge_matches(base, incoming):
    """Fusiona dues llistes de partits. 'incoming' té prioritat."""
    out = {match_key(m): m for m in base}
    out.update({match_key(m): m for m in incoming})
    merged = list(out.values())
    merged.sort(key=lambda m: (m["date"].split(".")[::-1], m["time"]))
    return merged


def refresh_calendar():
    """
    Baixa el Vereinsspielplan i el FUSIONA amb cache/spielplan.json.

    El Vereinsspielplan només llista partits d'avui endavant, igual que
    'Aktuelle Spiele'. Si substituíssim el cache a cada descàrrega perdríem
    tot l'històric i el post de resultats es quedaria sense els partits de
    principi de setmana. Per això acumulem.

    Retorna la llista fusionada, o el cache intacte si la descàrrega falla.
    """
    cached = cached_calendar(quiet=True)

    try:
        html = fetch({"a": "vs"})
    except Exception as e:
        print(f"  ! Vereinsspielplan failed: {e}")
        return cached

    try:
        fresh = parse_spielplan(html)
    except Exception as e:
        print(f"  ! parse Vereinsspielplan failed: {e}")
        return cached

    if len(fresh) < MIN_PLAUSIBLE:
        print(f"  ! només {len(fresh)} partits parsejats — es manté el cache "
              f"(esperats >= {MIN_PLAUSIBLE})")
        return cached

    merged = merge_matches(cached, fresh)
    added  = len(merged) - len(cached)

    os.makedirs(CACHE_DIR, exist_ok=True)
    payload = {"fetched": dt.datetime.now().isoformat(timespec="seconds"),
               "matches": merged}
    with open(SPIELPLAN, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    print(f"  ✓ calendari: {len(merged)} partits al cache "
          f"({len(fresh)} en viu, {added} nous)")
    return merged


def cached_calendar(quiet=False):
    """Llegeix cache/spielplan.json sense tocar la xarxa."""
    if not os.path.exists(SPIELPLAN):
        return []
    try:
        with open(SPIELPLAN, encoding="utf-8") as fh:
            data = json.load(fh)
        matches = data.get("matches", [])
        if not quiet:
            print(f"  · calendari en cache: {len(matches)} partits "
                  f"({data.get('fetched','?')})")
        return matches
    except Exception as e:
        print(f"  ! cache calendar failed: {e}")
        return []


# ------------------------------------------------------------- mapa d'actes

def _load_tg_map():
    if os.path.exists(TG_MAP):
        try:
            with open(TG_MAP, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return {}


def refresh_tg_map():
    """
    Llegeix 'Aktuelle Spiele' i acumula el mapa Spielnummer -> ID d'acta.
    Cal cridar-ho cada execució: el dilluns hi apunta el partit de dilluns,
    el divendres el de divendres, i el diumenge encara els té tots.
    """
    mapping = _load_tg_map()
    added = 0
    try:
        html = fetch({"a": "as"})
    except Exception as e:
        print(f"  ! Aktuelle Spiele failed: {e}")
        return mapping

    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        m = re.search(r"[?&]tg=(\d+)", a["href"])
        if not m:
            continue
        tg = m.group(1)
        node = a
        for _ in range(6):
            node = node.parent
            if node is None:
                break
            sm = _SPNR_RE.search(node.get_text(" ", strip=True))
            if sm:
                nr = sm.group(1)
                if mapping.get(nr) != tg:
                    mapping[nr] = tg
                    added += 1
                break

    if added:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(TG_MAP, "w", encoding="utf-8") as fh:
            json.dump(mapping, fh, indent=1, sort_keys=True)
    print(f"  · actes conegudes: {len(mapping)} ({added} noves)")
    return mapping


# ------------------------------------------------------------------ actes

# Marcador final seguit dels parcials: "4:2 (2:0)" a onze, però els juniors
# juguen per terços i llavors és "12:10 (4:3/9:4/10:6)".
_FT_HT = re.compile(
    r"(?<!\d)(\d{1,2})\s*:\s*(\d{1,2})(?!\d)"
    r"\s*\(\s*\d{1,2}\s*:\s*\d{1,2}"
    r"(?:\s*/\s*\d{1,2}\s*:\s*\d{1,2})*\s*\)"
)
# Entrada de gol del ticker: "80' 12:10 Tor España Torschütze ..."
# El marcador acumulat va ABANS de la paraula Tor.
_TICKER = re.compile(r"(?<!\d)(\d{1,2})\s*:\s*(\d{1,2})(?!\d)\s+Tor\b")


def telegram_score(tg):
    """Retorna (gols_local, gols_visitant) o None si encara no hi ha acta."""
    try:
        html = fetch({"tg": tg})
    except Exception as e:
        print(f"  ! acta {tg} failed: {e}")
        return None

    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)

    m = _FT_HT.search(text)
    if m:
        return int(m.group(1)), int(m.group(2))

    # Sense mitja part (juniors, futsal): el gol més recent del ticker
    # ja porta el marcador acumulat, que és el final.
    hits = _TICKER.findall(text)
    if hits:
        return int(hits[0][0]), int(hits[0][1])

    return None


def week_scores(spielnummern):
    """
    spielnummern: llista de Spielnummer (str).
    Retorna dict spielnummer -> {'score','home_goals','away_goals'}.
    """
    mapping = refresh_tg_map()
    scores = {}
    for nr in spielnummern:
        nr = str(nr).strip()
        if not nr:
            continue
        tg = mapping.get(nr)
        if not tg:
            print(f"  · {nr}: sense acta coneguda")
            continue
        res = telegram_score(tg)
        if res is None:
            print(f"  · {nr}: encara sense resultat")
            continue
        hg, ag = res
        scores[nr] = {"score": f"{hg}:{ag}", "home_goals": hg, "away_goals": ag}
        print(f"  · {nr}: {hg}:{ag}")
    print(f"  · scores found: {len(scores)}")
    return scores


# ------------------------------------------------------------------ CLI

def _cli_dump():
    os.makedirs(os.path.join(HERE, "debug"), exist_ok=True)
    for name, params in [("aktuelle", {"a": "as"}),
                         ("resultate", {"a": "rr"}),
                         ("spielplan", {"a": "vs"})]:
        try:
            html = fetch(params)
            path = os.path.join(HERE, "debug", f"{name}.html")
            open(path, "w", encoding="utf-8").write(html)
            print(f"  ✓ {name}: {len(html)} bytes -> {path}")
        except Exception as e:
            print(f"  ! {name}: {e}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    if cmd == "dump":
        _cli_dump()
    elif cmd == "calendar":
        for m in refresh_calendar()[:40]:
            print(f"  {m['dow']} {m['date']} {m['time']:>5}  "
                  f"{m['home']} - {m['away']}  [{m['spielnummer']}]")
    elif cmd == "scores":
        mapping = refresh_tg_map()
        for nr, tg in sorted(mapping.items()):
            print(f"  {nr} -> tg={tg}  {telegram_score(tg)}")
    else:
        print("== calendari ==")
        for m in refresh_calendar()[:15]:
            print(f"  {m['dow']} {m['date']} {m['time']:>5}  "
                  f"{m['home']} - {m['away']}  [{m['spielnummer']}]")
        print("== actes ==")
        refresh_tg_map()
