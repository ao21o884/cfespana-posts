# -*- coding: utf-8 -*-
"""
Modes:
  preview    → email + post + story  (dilluns)
  story_only → story sempre + post si hi ha canvis (dimecres/divendres)
  results    → email + post + story  (diumenge)
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
        headers={"Authorization": "Client-ID 546c25a59c58ad7"},
        data={"image": img_b64, "type": "base64"}, timeout=60
    )
    if r.status_code == 200:
        url = r.json()["data"]["link"]
        print(f"  · imgur: {url}"); return url
    print(f"  ! imgur failed: {r.text}"); return None


def buffer_create(channel_id, token, image_url, caption, is_story=False):
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
        ... on PostActionSuccess { post { id } }
        ... on MutationError { message }
      }
    }"""
    r = requests.post(url, json={"query": mutation}, headers=headers, timeout=120)
    r.raise_for_status()
    result = r.json().get("data", {}).get("createPost", {})
    if "message" in result:
        print(f"  ! Buffer ({mtype}): {result['message']}"); return False
    print(f"  → Buffer {mtype} ok (id: {result.get('post',{}).get('id')})"); return True


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
    """Compare current CSV with Wednesday snapshot (or Monday if no Wednesday)."""
    here    = os.path.dirname(os.path.abspath(__file__))
    current = os.path.join(here, "Verein-v1368.csv")
    # Friday compares with Wednesday, Wednesday compares with Monday
    wed_snap = os.path.join(here, "cache", "Verein-v1368-wednesday.csv")
    mon_snap = os.path.join(here, "cache", "Verein-v1368-monday.csv")
    snapshot = wed_snap if os.path.exists(wed_snap) else mon_snap
    cur_fp  = csv_fingerprint(current)
    snap_fp = csv_fingerprint(snapshot)
    print(f"  · current: {cur_fp}  snapshot: {snap_fp}")
    if cur_fp is None or snap_fp is None:
        print("  · cannot compare — assuming changes"); return True
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


if __name__ == "__main__":
    png      = sys.argv[1]
    mode     = sys.argv[2] if len(sys.argv) > 2 else "preview"
    cap_path = png.replace(".png", ".txt")
    caption  = open(cap_path, encoding="utf-8").read() if os.path.exists(cap_path) else ""

    token      = os.environ.get("BUFFER_TOKEN", "")
    channel_id = os.environ.get("BUFFER_CHANNEL_ID", "")
    image_url  = upload_to_imgur(png) if (token and channel_id) else None

    if mode == "results":
        # Diumenge: email + post al perfil + story amb resultats
        send_email(png, caption)
        if image_url:
            buffer_create(channel_id, token, image_url, caption, is_story=False)
            buffer_create(channel_id, token, image_url, "", is_story=True)

    elif mode == "story_only":
        # Dimecres: story sempre + post si hi ha canvis vs dilluns
        # Divendres: story sempre + post si hi ha canvis vs dimecres
        changes = has_changes()
        if image_url:
            if changes:
                print("  · changes found — publishing post + story")
                post_caption = "🔄 Änderungen diese Woche!\n\n" + caption
                buffer_create(channel_id, token, image_url, post_caption, is_story=False)
            else:
                print("  · no changes — story only")
            buffer_create(channel_id, token, image_url, "", is_story=True)
        # Save snapshot for next comparison
        import datetime as dt
        if dt.datetime.now().weekday() == 2:   # dimecres
            save_snapshot("wednesday")

    else:
        # Dilluns: email + post + story + snapshot
        send_email(png, caption)
        if image_url:
            buffer_create(channel_id, token, image_url, caption, is_story=False)
            buffer_create(channel_id, token, image_url, "", is_story=True)
        save_snapshot("monday")
