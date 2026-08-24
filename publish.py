# -*- coding: utf-8 -*-
"""
Modes:
  preview    → email + post + story  (dilluns)
  story_only → story sempre + post si hi ha canvis (dimecres/divendres)
  results    → email + post + story  (diumenge)

Canvis respecte de la versió antiga:
  · buffer_create() detecta els errors GraphQL que arriben amb HTTP 200.
  · Si Imgur falla, el script surt amb codi != 0 en comptes de callar.
  · La detecció de canvis usa cache/spielplan.json (calendari en viu),
    no el CSV, que ja no és la font principal.
"""
import os, sys, time, requests, base64, io, json, hashlib, shutil

HERE      = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "cache")
SPIELPLAN = os.path.join(CACHE_DIR, "spielplan.json")


def send_email(png, caption):
    import smtplib
    from email.message import EmailMessage
    sender    = os.environ.get("EMAIL_FROM", "")
    password  = os.environ.get("EMAIL_PASSWORD", "")
    recipient = os.environ.get("EMAIL_TO", "")
    if not (sender and password and recipient):
        print("  · email not set — skipping"); return False
    fname   = os.path.basename(png)
    subject = "⚽ C.F. España — Resultate" if "results" in fname else "⚽ C.F. España — Partits de la setmana"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = recipient
    msg.set_content(caption)
    with open(png, "rb") as fh:
        msg.add_attachment(fh.read(), maintype="image", subtype="png",
                           filename=os.path.basename(png))
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls(); s.login(sender, password); s.send_message(msg)
    print(f"  → email sent to {recipient}"); return True


def upload_to_imgur(png, tries=4):
    """
    Puja la imatge a Imgur i retorna l'URL públic.

    Imgur dona 503 i 429 amb certa freqüència sense que hi hagi res mal fet,
    així que reintentem amb espera creixent. Només els errors permanents
    (401, 403, imatge invàlida) fallen a la primera.
    """
    from PIL import Image
    img = Image.open(png).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    print(f"  · size: {len(buf.getvalue())//1024}KB")

    client_id = os.environ.get("IMGUR_CLIENT_ID", "546c25a59c58ad7")
    transient = {429, 500, 502, 503, 504}
    last = ""

    for n in range(tries):
        try:
            r = requests.post(
                "https://api.imgur.com/3/image",
                headers={"Authorization": f"Client-ID {client_id}"},
                data={"image": img_b64, "type": "base64"}, timeout=60
            )
        except Exception as e:
            last = f"excepció: {e}"
            if n + 1 < tries:
                wait = 5 * (n + 1)
                print(f"  · imgur {last} — reintent en {wait}s")
                time.sleep(wait)
            continue

        if r.status_code == 200:
            url = r.json()["data"]["link"]
            print(f"  · imgur: {url}")
            return url

        last = f"{r.status_code}: {r.text[:200]}"
        if r.status_code in transient and n + 1 < tries:
            wait = 5 * (n + 1)
            print(f"  · imgur {r.status_code} — reintent en {wait}s")
            time.sleep(wait)
            continue
        break

    raise RuntimeError(f"Imgur ha fallat després de {tries} intents — {last}")


def github_raw_url(png, tries=5):
    """
    URL pública de la imatge servida pel propi repositori.

    Requereix que el PNG ja estigui commitejat i pujat, i que el repo sigui
    públic. IMAGE_BASE_URL l'omple el workflow amb
    https://raw.githubusercontent.com/<repo>/<branca>/out

    Verifiquem que respon 200 abans de donar-la per bona: després d'un push
    la CDN de GitHub pot trigar uns segons a servir el fitxer.
    """
    base = os.environ.get("IMAGE_BASE_URL", "").rstrip("/")
    if not base:
        return None

    url = f"{base}/{os.path.basename(png)}"
    for n in range(tries):
        try:
            r = requests.head(url, timeout=20, allow_redirects=True)
            if r.status_code == 200:
                print(f"  · github raw: {url}")
                return url
            last = r.status_code
        except Exception as e:
            last = e
        if n + 1 < tries:
            print(f"  · github raw encara no disponible ({last}) — espero 5s")
            time.sleep(5)
    print(f"  ! github raw no disponible: {url}")
    return None


def public_image_url(png):
    """
    URL pública per passar a Buffer.

    Primer el repositori (gratuït, sense límits, i el fitxer ja hi és);
    Imgur com a reserva. Imgur ha demostrat ser el punt fràgil de tota la
    cadena: un 503 seu deixava la publicació sencera sense fer.
    """
    url = github_raw_url(png)
    if url:
        return url

    print("  · provant Imgur com a reserva")
    return upload_to_imgur(png)


def buffer_create(channel_id, token, image_url, caption, is_story=False):
    """
    Crea un post a la cua de Buffer. Llança RuntimeError si no s'ha creat res.

    Buffer respon HTTP 200 fins i tot quan el token ha caducat: l'error va
    dins de payload['errors'] i 'data' ve buit o nul. Sense aquesta
    comprovació, un token mort sembla una publicació correcta.
    """
    url     = "https://api.buffer.com"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    mtype   = "story" if is_story else "post"
    # shouldShareToFeed és obligatori des d'un canvi de l'API de Buffer.
    # Per a un post normal va a true; per a una story, false (si no,
    # la story es duplicaria al feed).
    share_to_feed = "false" if is_story else "true"

    mutation = """mutation CreatePost {
      createPost(input: {
        text: """ + json.dumps(caption if not is_story else "") + """
        channelId: """ + json.dumps(channel_id) + """
        schedulingType: automatic
        mode: addToQueue
        metadata: { instagram: { type: """ + mtype + """
                                 shouldShareToFeed: """ + share_to_feed + """ } }
        assets: [{ image: { url: """ + json.dumps(image_url) + """ } }]
      }) {
        __typename
        ... on PostActionSuccess { post { id } }
        ... on MutationError { message }
      }
    }"""

    r = requests.post(url, json={"query": mutation}, headers=headers, timeout=120)

    if r.status_code != 200:
        raise RuntimeError(f"Buffer HTTP {r.status_code}: {r.text[:600]}")

    try:
        payload = r.json()
    except ValueError:
        raise RuntimeError(f"Buffer: resposta no-JSON: {r.text[:600]}")

    if payload.get("errors"):
        raise RuntimeError(f"Buffer GraphQL errors ({mtype}): "
                           f"{json.dumps(payload['errors'], ensure_ascii=False)[:800]}")

    result = (payload.get("data") or {}).get("createPost")
    if not result:
        raise RuntimeError(f"Buffer: resposta sense createPost ({mtype}): "
                           f"{json.dumps(payload, ensure_ascii=False)[:800]}")

    if result.get("__typename") == "MutationError" or "message" in result:
        raise RuntimeError(f"Buffer {mtype} rebutjat: {result.get('message')}")

    post_id = (result.get("post") or {}).get("id")
    if not post_id:
        raise RuntimeError(f"Buffer {mtype}: sense id a la resposta: "
                           f"{json.dumps(payload, ensure_ascii=False)[:800]}")

    print(f"  → Buffer {mtype} ok (id: {post_id})")
    return True


def spielplan_fingerprint(path):
    """Hash dels camps rellevants del calendari."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        rows = ["|".join([m.get("date",""), m.get("time",""), m.get("home",""),
                          m.get("away",""), m.get("venue","")])
                for m in data.get("matches", [])]
        return hashlib.md5("\n".join(sorted(rows)).encode()).hexdigest()
    except Exception as e:
        print(f"  ! fingerprint error: {e}")
        return None


def has_changes():
    """
    Compara el calendari actual amb la instantània de dimecres (o dilluns).
    Si no es pot comparar, retorna False: publicar un post de canvis fals
    cada setmana és pitjor que no publicar-lo.
    """
    wed = os.path.join(CACHE_DIR, "spielplan-wednesday.json")
    mon = os.path.join(CACHE_DIR, "spielplan-monday.json")
    snapshot = wed if os.path.exists(wed) else mon
    cur_fp  = spielplan_fingerprint(SPIELPLAN)
    snap_fp = spielplan_fingerprint(snapshot)
    print(f"  · current: {cur_fp}  snapshot: {snap_fp}")
    if cur_fp is None or snap_fp is None:
        print("  ! no es pot comparar — no es publica post de canvis")
        return False
    changed = cur_fp != snap_fp
    print(f"  · changed: {changed}")
    return changed


def save_snapshot(day):
    """day = 'monday' o 'wednesday'"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    dst = os.path.join(CACHE_DIR, f"spielplan-{day}.json")
    if os.path.exists(SPIELPLAN):
        shutil.copy2(SPIELPLAN, dst)
        print(f"  · snapshot: cache/spielplan-{day}.json")
    else:
        print("  ! no hi ha spielplan.json per desar com a instantània")


def main():
    png      = sys.argv[1]
    mode     = sys.argv[2] if len(sys.argv) > 2 else "preview"
    cap_path = png.replace(".png", ".txt")
    caption  = open(cap_path, encoding="utf-8").read() if os.path.exists(cap_path) else ""

    token      = os.environ.get("BUFFER_TOKEN", "")
    channel_id = os.environ.get("BUFFER_CHANNEL_ID", "")

    if not (token and channel_id):
        print("  ! BUFFER_TOKEN / BUFFER_CHANNEL_ID no configurats")
        send_email(png, caption)
        raise SystemExit(1)

    image_url = public_image_url(png)

    if mode == "results":
        send_email(png, caption)
        buffer_create(channel_id, token, image_url, caption, is_story=False)
        buffer_create(channel_id, token, image_url, "", is_story=True)

    elif mode == "story_only":
        if has_changes():
            print("  · hi ha canvis — post + story")
            buffer_create(channel_id, token, image_url,
                          "🔄 Änderungen diese Woche!\n\n" + caption, is_story=False)
        else:
            print("  · sense canvis — només story")
        buffer_create(channel_id, token, image_url, "", is_story=True)
        import datetime as dt
        if dt.datetime.now().weekday() == 2:
            save_snapshot("wednesday")

    else:
        send_email(png, caption)
        buffer_create(channel_id, token, image_url, caption, is_story=False)
        buffer_create(channel_id, token, image_url, "", is_story=True)
        save_snapshot("monday")


if __name__ == "__main__":
    main()
