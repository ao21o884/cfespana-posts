# -*- coding: utf-8 -*-
import os, sys, requests, base64, io


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


def post_buffer(png, caption):
    token      = os.environ.get("BUFFER_TOKEN", "")
    channel_id = os.environ.get("BUFFER_CHANNEL_ID", "")
    if not (token and channel_id):
        print("  · BUFFER_TOKEN / BUFFER_CHANNEL_ID not set — skipping Buffer"); return False

    # Compress image to JPEG to reduce size for upload
    from PIL import Image
    img = Image.open(png).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=60, optimize=True)
    img_bytes = buf.getvalue()
    img_b64   = base64.b64encode(img_bytes).decode()
    print(f"  · compressed size: {len(img_bytes)//1024}KB")

    # Upload to imgur anonymously (no auth needed for anonymous upload)
    imgur_resp = requests.post(
        "https://api.imgur.com/3/image",
        headers={"Authorization": "Client-ID 546c25a59c58ad7"},
        data={"image": img_b64, "type": "base64"},
        timeout=60
    )
    if imgur_resp.status_code == 200:
        image_url = imgur_resp.json()["data"]["link"]
        print(f"  · image uploaded to imgur: {image_url}")
    else:
        print(f"  ! imgur upload failed: {imgur_resp.text}")
        return False

    url     = "https://api.buffer.com"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    mutation = """
    mutation CreatePost {
      createPost(
        input: {
          text: """ + json_str(caption) + """
          channelId: """ + json_str(channel_id) + """
          schedulingType: automatic
          mode: addToQueue
          metadata: {
            instagram: {
              type: post
              shouldShareToFeed: true
            }
          }
          assets: [{ image: { url: """ + json_str(image_url) + """ } }]
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
        print(f"  ! Buffer error: {result['message']}"); return False
    post_id = result.get("post", {}).get("id")
    print(f"  → published to Instagram via Buffer (post id: {post_id})"); return True


def json_str(s):
    import json; return json.dumps(s)


if __name__ == "__main__":
    png      = sys.argv[1]
    cap_path = png.replace(".png", ".txt")
    caption  = open(cap_path, encoding="utf-8").read() if os.path.exists(cap_path) else ""
    ok = False
    ok = send_email(png, caption) or ok
    ok = post_buffer(png, caption) or ok
    if not ok:
        print("No channel configured.")
