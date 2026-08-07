# -*- coding: utf-8 -*-
"""
Publishing layer for C.F. España post generator.
Sends image + caption via email AND publishes to Instagram via Buffer API.
"""
import os
import sys
import base64
import requests


def send_email(png, caption):
    import smtplib
    from email.message import EmailMessage

    sender    = os.environ.get("EMAIL_FROM", "")
    password  = os.environ.get("EMAIL_PASSWORD", "")
    recipient = os.environ.get("EMAIL_TO", "")

    if not (sender and password and recipient):
        print("  · email secrets not set — skipping email")
        return False

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
        s.starttls()
        s.login(sender, password)
        s.send_message(msg)

    print(f"  → email sent to {recipient}")
    return True


def post_buffer(png, caption):
    """Publish image + caption to Instagram via Buffer API."""
    token      = os.environ.get("BUFFER_TOKEN", "")
    channel_id = os.environ.get("BUFFER_CHANNEL_ID", "")

    if not (token and channel_id):
        print("  · BUFFER_TOKEN / BUFFER_CHANNEL_ID not set — skipping Buffer")
        return False

    # Buffer GraphQL API endpoint
    url     = "https://api.buffer.com/graphql"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }

    # Step 1: upload image as base64
    with open(png, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    # Buffer createPost mutation with image
    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        post {
          id
          status
        }
        errors {
          message
        }
      }
    }
    """

    variables = {
        "input": {
            "channelId": channel_id,
            "text":      caption,
            "media": [{
                "type":  "image",
                "url":   None,
                "data":  img_b64,
            }],
            "publishNow": True,
        }
    }

    r = requests.post(url, json={"query": mutation, "variables": variables},
                      headers=headers, timeout=120)
    r.raise_for_status()
    data = r.json()

    errors = data.get("data", {}).get("createPost", {}).get("errors", [])
    if errors:
        print(f"  ! Buffer error: {errors}")
        return False

    post_id = data.get("data", {}).get("createPost", {}).get("post", {}).get("id")
    print(f"  → published to Instagram via Buffer (post id: {post_id})")
    return True


if __name__ == "__main__":
    png     = sys.argv[1]
    cap_path = png.replace(".png", ".txt")
    caption  = open(cap_path, encoding="utf-8").read() if os.path.exists(cap_path) else ""

    ok = False
    ok = send_email(png, caption)    or ok
    ok = post_buffer(png, caption)   or ok

    if not ok:
        print("No channel configured — image saved in out/ only.")
