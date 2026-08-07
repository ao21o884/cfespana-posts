# -*- coding: utf-8 -*-
"""
Publishing layer for C.F. España post generator.
Sends image + caption via email AND publishes to Instagram via Buffer API.
"""
import os, sys, requests


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
    repo       = os.environ.get("GITHUB_REPOSITORY", "")

    if not (token and channel_id):
        print("  · BUFFER_TOKEN / BUFFER_CHANNEL_ID not set — skipping Buffer")
        return False

    # Build public raw GitHub URL for the image
    fname     = os.path.basename(png)
    image_url = f"https://raw.githubusercontent.com/{repo}/main/out/{fname}"
    print(f"  · image URL: {image_url}")

    url     = "https://api.buffer.com"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }

    # Use correct Buffer API v2 mutation with assets
    mutation = """
    mutation CreatePost {
      createPost(
        input: {
          text: """ + json_str(caption) + """
          channelId: """ + json_str(channel_id) + """
          schedulingType: automatic
          mode: addToQueue
          assets: [
            {
              image: {
                url: """ + json_str(image_url) + """
              }
            }
          ]
        }
      ) {
        ... on PostActionSuccess {
          post {
            id
            text
          }
        }
        ... on MutationError {
          message
        }
      }
    }
    """

    r = requests.post(url, json={"query": mutation},
                      headers=headers, timeout=120)
    r.raise_for_status()
    data = r.json()
    print(f"  · Buffer response: {data}")

    result = data.get("data", {}).get("createPost", {})
    if "message" in result:
        print(f"  ! Buffer error: {result['message']}")
        return False

    post_id = result.get("post", {}).get("id")
    print(f"  → published to Instagram via Buffer (post id: {post_id})")
    return True


def json_str(s):
    """Escape a string for inline GraphQL."""
    import json
    return json.dumps(s)


if __name__ == "__main__":
    png      = sys.argv[1]
    cap_path = png.replace(".png", ".txt")
    caption  = open(cap_path, encoding="utf-8").read() if os.path.exists(cap_path) else ""

    ok = False
    ok = send_email(png, caption)  or ok
    ok = post_buffer(png, caption) or ok

    if not ok:
        print("No channel configured — image saved in out/ only.")
