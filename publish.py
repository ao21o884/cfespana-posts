# -*- coding: utf-8 -*-
"""
Publishing layer for C.F. España post generator.
- Email delivery
- Buffer: immediate post + story
- Story repeats: Wednesday 9:00 and Friday 9:00 if first match is later
"""
import os, sys, requests, base64, io, datetime, json


def send_email(png, caption):
    import smtplib
    from email.message import EmailMessage
    sender    = os.environ.get("EMAIL_FROM", "")
    password  = os.environ.get("EMAIL_PASSWORD", "")
    recipient = os.environ.get("EMAIL_TO", "")
    if not (sender and password and recipient):
        print("  · email secrets not set — skipping email"); return False
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
    """Upload image to Imgur and return public URL."""
    from PIL import Image
    img = Image.open(png).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    print(f"  · compressed size: {len(buf.getvalue())//1024}KB")

    r = requests.post(
        "https://api.imgur.com/3/image",
        headers={"Authorization": "Client-ID 546c25a59c58ad7"},
        data={"image": img_b64, "type": "base64"},
        timeout=60
    )
    if r.status_code == 200:
        url = r.json()["data"]["link"]
        print(f"  · uploaded to imgur: {url}")
        return url
    print(f"  ! imgur upload failed: {r.text}")
    return None


def buffer_create(channel_id, token, image_url, caption, is_story=False):
    """Create a post or story via Buffer API."""
    url     = "https://api.buffer.com"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    media_type = "story" if is_story else "post"

    mutation = """
    mutation CreatePost {
      createPost(
        input: {
          text: """ + json.dumps(caption if not is_story else "") + """
          channelId: """ + json.dumps(channel_id) + """
          schedulingType: automatic
          mode: addToQueue
          metadata: {
            instagram: {
              type: """ + media_type + """
            }
          }
          assets: [{ image: { url: """ + json.dumps(image_url) + """ } }]
        }
      ) {
        ... on PostActionSuccess { post { id } }
        ... on MutationError { message }
      }
    }
    """

    r = requests.post(url, json={"query": mutation}, headers=headers, timeout=120)
    r.raise_for_status()
    data   = r.json()
    result = data.get("data", {}).get("createPost", {})
    if "message" in result:
        print(f"  ! Buffer error ({media_type}): {result['message']}"); return False
    post_id = result.get("post", {}).get("id")
    print(f"  → Buffer {media_type} created (id: {post_id})"); return True


def first_match_dt():
    """Read first match datetime from out/*.txt caption or CSV."""
    import glob, re, datetime as dt
    # Try to find first match date from CSV
    csv_path = os.path.join(os.path.dirname(__file__) if '__file__' in dir() else ".", "Verein-v1368.csv")
    if not os.path.exists(csv_path):
        return None
    try:
        import csv, io as _io
        text = open(csv_path, encoding="latin-1", errors="replace").read()
        reader = csv.DictReader(_io.StringIO(text), delimiter=';')
        today = dt.date.today()
        # Get Monday of current week
        monday = today - dt.timedelta(days=today.weekday())
        sunday = monday + dt.timedelta(days=6)
        earliest = None
        for row in reader:
            datum = row.get("Spieldatum","").strip()
            zeit  = row.get("Spielzeit","").strip()
            if not datum or not zeit: continue
            try:
                d_parts = datum.split(".")
                d = dt.date(int(d_parts[2]), int(d_parts[1]), int(d_parts[0]))
                if not (monday <= d <= sunday): continue
                h, m = map(int, zeit.split(":"))
                match_dt = dt.datetime(d.year, d.month, d.day, h, m)
                if earliest is None or match_dt < earliest:
                    earliest = match_dt
            except Exception:
                continue
        return earliest
    except Exception as e:
        print(f"  ! could not read first match: {e}")
        return None


def post_buffer(png, caption, is_results=False):
    """Publish post + story to Instagram via Buffer."""
    token      = os.environ.get("BUFFER_TOKEN", "")
    channel_id = os.environ.get("BUFFER_CHANNEL_ID", "")
    if not (token and channel_id):
        print("  · BUFFER_TOKEN / BUFFER_CHANNEL_ID not set — skipping Buffer"); return False

    image_url = upload_to_imgur(png)
    if not image_url: return False

    ok = True
    # Post normal
    ok = buffer_create(channel_id, token, image_url, caption, is_story=False) and ok

    # Story (not for results)
    if not is_results:
        ok = buffer_create(channel_id, token, image_url, "", is_story=True) and ok

    return ok


def post_story_only(png):
    """Publish only a story (for Wednesday/Friday repeats)."""
    token      = os.environ.get("BUFFER_TOKEN", "")
    channel_id = os.environ.get("BUFFER_CHANNEL_ID", "")
    if not (token and channel_id):
        print("  · BUFFER_TOKEN / BUFFER_CHANNEL_ID not set — skipping story"); return False

    image_url = upload_to_imgur(png)
    if not image_url: return False
    return buffer_create(channel_id, token, image_url, "", is_story=True)


if __name__ == "__main__":
    import datetime as dt

    png      = sys.argv[1]
    cap_path = png.replace(".png", ".txt")
    caption  = open(cap_path, encoding="utf-8").read() if os.path.exists(cap_path) else ""
    mode     = sys.argv[2] if len(sys.argv) > 2 else "preview"
    is_story_only = (mode == "story")
    is_results    = ("results" in os.path.basename(png))

    ok = False

    if is_story_only:
        # Wednesday / Friday repeat — check if first match is later today
        first_match = first_match_dt()
        now         = dt.datetime.now()
        print(f"  · First match: {first_match}")
        print(f"  · Now: {now}")
        if first_match and first_match <= now:
            print("  · First match already started — skipping story"); sys.exit(0)
        ok = post_story_only(png)
    else:
        ok = send_email(png, caption) or ok
        ok = post_buffer(png, caption, is_results=is_results) or ok

    if not ok:
        print("No channel configured.")
