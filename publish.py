# -*- coding: utf-8 -*-
"""
Modes:
  preview    → email + post + story  (dilluns)
  story_only → story sempre + post si hi ha canvis (dimecres/divendres)
  results    → email + post + story  (diumenge)

CANVIS respecte de la versió anterior:
  · buffer_create() ara detecta els errors GraphQL que arriben amb HTTP 200
    i llança excepció en comptes d'imprimir "ok (id: None)".
  · Si Imgur falla, el script surt amb codi != 0 en comptes de callar.
  · has_changes() ja no assumeix "hi ha canvis" quan no pot comparar.
"""
import os, sys, requests, base64, io, json, hashlib, shutil


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


def upload_to_imgur(png):
    from PIL import Image
    img = Image.open(png).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    print(f"  · size: {len(buf.getvalue())//1024}KB")
    r = requests.post(
        "https://api.imgur.com/3/image",
        headers={"Authorization": f"Client-ID {os.environ.get('IMGUR_CLIENT_ID', '546c25a59c58ad7')}"},
        data={"image": img_b64, "type": "base64"}, timeout=60
    )
    if r.status_code == 200:
        url = r.json()["data"]["link"]
        print(f"  · imgur: {url}"); return url
    raise RuntimeError(f"Imgur {r.status_code}: {r.text[:400]}")


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
    mutation = """mutation CreatePost {
      createPost(input: {
        text: """ + json.dumps(caption if not is_story else "") + """
        channelId: """ + json.dumps(channel_id) + """
        schedulingType: automatic
        mode: addToQueue
        metadata: { instagram: { type: """ + mtype + """ } }
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


def csv_fingerprint(path):
    """Hash of match-relevant CSV fields."""
    import csv as _csv, io as _io
    if not os.path.exists(path): return None
    try:
        text   = open(path, encoding="latin-1", errors="replace").read()
        reader = _csv.DictReader(_io.StringIO(text), delimiter=';')
        rows   = []
        for row in reader:
            rows.append("|".join([
                row.get("Spieldatum","").strip(),
                row.get("Spielzeit","").strip(),
                row.get("Teamname A","").strip(),
                row.get("Teamname B","").strip(),
                row.get("Spielort","").strip(),
            ]))
        return hashlib.md5("\n".join(sorted(rows)).encode()).hexdigest()
    except Exception as e:
        print(f"  ! fingerprint error: {e}"); return None


def has_changes():
    """
    Compara el CSV actual amb la instantània de dimecres (o dilluns).
    Si no es pot comparar, retorna False: publicar un post de canvis
    fals cada setmana és pitjor que no publicar-lo.
    """
    here    = os.path.dirname(os.path.abspath(__file__))
    current = os.path.join(here, "Verein-v1368.csv")
    wed_snap = os.path.join(here, "cache", "Verein-v1368-wednesday.csv")
    mon_snap = os.path.join(here, "cache", "Verein-v1368-monday.csv")
    snapshot = wed_snap if os.path.exists(wed_snap) else mon_snap
    cur_fp  = csv_fingerprint(current)
    snap_fp = csv_fingerprint(snapshot)
    print(f"  · current: {cur_fp}  snapshot: {snap_fp}")
    if cur_fp is None or snap_fp is None:
        print("  ! no es pot comparar (falta CSV) — no es publica post de canvis")
        return False
    changed = cur_fp != snap_fp
    print(f"  · changed: {changed}"); return changed


def save_snapshot(day):
    """Save CSV snapshot for comparison. day = 'monday' or 'wednesday'."""
    here     = os.path.dirname(os.path.abspath(__file__))
    src      = os.path.join(here, "Verein-v1368.csv")
    cache    = os.path.join(here, "cache")
    os.makedirs(cache, exist_ok=True)
    dst      = os.path.join(cache, f"Verein-v1368-{day}.csv")
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"  · snapshot saved: cache/Verein-v1368-{day}.csv")
    else:
        print("  ! no hi ha CSV per desar com a instantània")


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

    image_url = upload_to_imgur(png)

    if mode == "results":
        send_email(png, caption)
        buffer_create(channel_id, token, image_url, caption, is_story=False)
        buffer_create(channel_id, token, image_url, "", is_story=True)

    elif mode == "story_only":
        if has_changes():
            print("  · changes found — publishing post + story")
            buffer_create(channel_id, token, image_url,
                          "🔄 Änderungen diese Woche!\n\n" + caption, is_story=False)
        else:
            print("  · no changes — story only")
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
