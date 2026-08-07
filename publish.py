# -*- coding: utf-8 -*-
"""
Publishing layer for the C.F. España post generator.

Channels (driven by GitHub Secrets / env vars):

  EMAIL   EMAIL_FROM   + EMAIL_TO + EMAIL_PASSWORD
          -> sends image + caption to your inbox via Gmail SMTP.
             Use a Gmail "App Password" (not your normal password).
             Works with any Gmail address.

  INSTAGRAM  IG_USER_ID + IG_TOKEN + IMAGE_BASE_URL
          -> posts automatically via Meta Graph API.
             Requires a Business/Creator Instagram account linked to a
             Facebook Page, and a long-lived access token.
             IMAGE_BASE_URL must be a public https URL (e.g. raw.githubusercontent.com).

Usage:
    python publish.py out/cfespana_preview_2026-08-17.png
"""
import os
import sys
import time

GRAPH = "https://graph.facebook.com/v21.0"


# ──────────────────────────────────────────────────── email
def send_email(png, caption):
    import smtplib
    from email.message import EmailMessage

    sender   = os.environ.get("EMAIL_FROM", "")
    password = os.environ.get("EMAIL_PASSWORD", "")
    recipient = os.environ.get("EMAIL_TO", "")

    if not (sender and password and recipient):
        print("  · EMAIL_FROM / EMAIL_PASSWORD / EMAIL_TO not set — skipping email")
        return False

    # figure out mode from filename for a nice subject line
    fname = os.path.basename(png)
    if "results" in fname:
        subject = f"⚽ C.F. España — Resultats de la setmana"
    else:
        subject = f"⚽ C.F. España — Partits de la setmana"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = recipient

    # plain-text body = the Instagram caption
    msg.set_content(caption)

    # attach the image so you can forward/save it directly
    with open(png, "rb") as fh:
        img_data = fh.read()
    msg.add_attachment(img_data, maintype="image", subtype="png",
                       filename=os.path.basename(png))

    # Gmail SMTP with TLS
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(sender, password)
        s.send_message(msg)

    print(f"  → email sent to {recipient}")
    return True


# ──────────────────────────────────────────────────── instagram
def post_instagram(png, caption):
    import requests
    ig   = os.environ.get("IG_USER_ID", "")
    tok  = os.environ.get("IG_TOKEN", "")
    base = os.environ.get("IMAGE_BASE_URL", "").rstrip("/")
    if not (ig and tok and base):
        print("  · IG_USER_ID / IG_TOKEN / IMAGE_BASE_URL not set — skipping Instagram")
        return False

    image_url = f"{base}/{os.path.basename(png)}"

    r = requests.post(f"{GRAPH}/{ig}/media",
                      data={"image_url": image_url, "caption": caption,
                            "access_token": tok}, timeout=90)
    r.raise_for_status()
    cid = r.json()["id"]

    for _ in range(20):
        st = requests.get(f"{GRAPH}/{cid}",
                          params={"fields": "status_code", "access_token": tok},
                          timeout=60).json().get("status_code")
        if st == "FINISHED":
            break
        if st == "ERROR":
            raise RuntimeError(f"Meta rejected the container: {r.text}")
        time.sleep(5)

    p = requests.post(f"{GRAPH}/{ig}/media_publish",
                      data={"creation_id": cid, "access_token": tok}, timeout=90)
    p.raise_for_status()
    print(f"  → published to Instagram: {p.json()}")
    return True


# ──────────────────────────────────────────────────── main
if __name__ == "__main__":
    png     = sys.argv[1]
    caption = open(png.replace(".png", ".txt"), encoding="utf-8").read()

    ok = False
    ok = send_email(png, caption)    or ok
    ok = post_instagram(png, caption) or ok

    if not ok:
        print("No channel configured — image + caption saved in out/ only.")
