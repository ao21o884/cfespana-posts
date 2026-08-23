# -*- coding: utf-8 -*-
"""
Capa de xarxa i lectura de resultats del matchcenter FVBJ/AFBJ.

Substitueix week_scores() de sources.py.

Estratègia:
  1. Sessió amb capçaleres de navegador + cookies (evita el 403).
  2. Llegeix 'Aktuelle Spiele' i extreu el mapa Spielnummer -> ID de Telegramm.
  3. Persisteix el mapa a cache/tg_map.json  <-- clau: els partits passats
     desapareixen d'Aktuelle Spiele, però el Telegramm és permanent.
  4. Llegeix el marcador de cada pàgina de Telegramm.

Ús directe per depurar:
    python matchcenter.py                 # prova la connexió i llista marcadors
    python matchcenter.py dump            # desa l'HTML cru a debug/
"""
import os, re, json, sys, time
import requests
from bs4 import BeautifulSoup

HERE      = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "cache")
TG_MAP    = os.path.join(CACHE_DIR, "tg_map.json")

BASE = "https://matchcenter.fvbj-afbj.ch/default.aspx"
CLUB = {"v": "1368", "oid": "6", "lng": "1"}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36")

_session = None


def session():
    """Sessió reutilitzable, escalfada amb una visita a la portada del club."""
    global _session
    if _session is not None:
        return _session
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-CH,de;q=0.9,fr;q=0.8,en;q=0.7",
        "Upgrade-Insecure-Requests": "1",
    })
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


# ---------------------------------------------------------------- mapa tg

def _load_tg_map():
    if os.path.exists(TG_MAP):
        try:
            with open(TG_MAP, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return {}


def _save_tg_map(mapping):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(TG_MAP, "w", encoding="utf-8") as fh:
        json.dump(mapping, fh, indent=1, sort_keys=True)


def refresh_tg_map():
    """
    Llegeix 'Aktuelle Spiele' i actualitza (sense esborrar) el mapa
    Spielnummer -> tg. Cridar-ho cada execució, inclosa la de dilluns:
    així el diumenge encara tens els IDs dels partits de dilluns i divendres.
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
        for _ in range(6):                      # puja fins al bloc del partit
            node = node.parent
            if node is None:
                break
            sm = re.search(r"Spielnummer\s*:?\s*(\d+)",
                           node.get_text(" ", strip=True))
            if sm:
                spielnr = sm.group(1)
                if mapping.get(spielnr) != tg:
                    mapping[spielnr] = tg
                    added += 1
                break

    if added:
        _save_tg_map(mapping)
    print(f"  · tg map: {len(mapping)} partits ({added} nous)")
    return mapping


# ------------------------------------------------------------- telegramm

# Marcador final seguit de la mitja part entre parèntesis: "4:2 (2:0)"
_FT_HT = re.compile(r"(?<!\d)(\d{1,2})\s*:\s*(\d{1,2})(?!\d)\s*\(\s*\d{1,2}\s*:\s*\d{1,2}\s*\)")
# Entrada de gol del ticker amb el marcador acumulat
_TICKER = re.compile(r"Tor\s+(\d{1,2})\s*:\s*(\d{1,2})(?!\d)")


def telegram_score(tg):
    """Retorna (home_goals, away_goals) o None si el partit no s'ha jugat."""
    try:
        html = fetch({"tg": tg})
    except Exception as e:
        print(f"  ! telegramm {tg} failed: {e}")
        return None

    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)

    m = _FT_HT.search(text)
    if m:
        return int(m.group(1)), int(m.group(2))

    # Sense mitja part (juniors, futsal): el gol més recent del ticker
    # porta el marcador acumulat, que és el final.
    hits = _TICKER.findall(text)
    if hits:
        return int(hits[0][0]), int(hits[0][1])

    return None


# ------------------------------------------------------------ API pública

def week_scores(spielnummern):
    """
    spielnummern: llista de Spielnummer (str) dels partits de la setmana.
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
            print(f"  · {nr}: sense tg conegut")
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


# ------------------------------------------------------------------ debug

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "dump":
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
        sys.exit(0)

    mapping = refresh_tg_map()
    for nr, tg in sorted(mapping.items()):
        print(f"  {nr} -> tg={tg}  {telegram_score(tg)}")
