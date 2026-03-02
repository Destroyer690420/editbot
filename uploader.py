"""
uploader.py
Posts a local video file to Instagram as a Reel using the Graph API's
resumable upload protocol. No third-party hosting required.

Flow:
  1. POST /{ig_user_id}/media  →  get container_id + upload_uri
  2. POST upload_uri (raw bytes)  →  video uploaded to Facebook servers
  3. Poll /{container_id}?fields=status_code  →  wait for FINISHED
  4. POST /{ig_user_id}/media_publish  →  Reel goes live
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

IG_USER_ID = os.getenv("IG_USER_ID", "")
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")

GRAPH_API_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# How long (seconds) to wait for the container to become FINISHED
UPLOAD_TIMEOUT = 600
POLL_INTERVAL = 15


# ────────────────────────────────────────────────────────────
# Internal helpers
# ────────────────────────────────────────────────────────────

def _init_upload_session(caption: str) -> dict:
    """
    Step 1 — Create a resumable-upload media container.
    Returns the raw API dict: {"id": "<container_id>", "uri": "<upload_url>"}
    """
    url = f"{GRAPH_BASE}/{IG_USER_ID}/media"
    params = {
        "media_type": "REELS",
        "upload_type": "resumable",
        "caption": caption,
        "share_to_feed": "true",
        "access_token": IG_ACCESS_TOKEN,
    }
    resp = requests.post(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "id" not in data or "uri" not in data:
        raise RuntimeError(f"Unexpected init response: {data}")
    return data


def _stream_video(upload_uri: str, file_path: str) -> None:
    """
    Step 2 — Stream raw video bytes to the resumable upload URI.
    Instagram expects the entire file in a single chunk for typical Reel sizes.
    """
    file_size = os.path.getsize(file_path)
    print(f"    Uploading {file_size / (1024 * 1024):.1f} MB to Facebook servers…")

    with open(file_path, "rb") as fh:
        headers = {
            "Authorization": f"OAuth {IG_ACCESS_TOKEN}",
            "offset": "0",
            "file_size": str(file_size),
            "Content-Type": "video/mp4",
        }
        resp = requests.post(
            upload_uri,
            headers=headers,
            data=fh,
            timeout=600,  # large file may take a while
        )
    resp.raise_for_status()


def _wait_until_finished(container_id: str) -> None:
    """
    Step 3 — Poll the container until status_code == FINISHED.
    Raises RuntimeError on ERROR or TimeoutError if it takes too long.
    """
    url = f"{GRAPH_BASE}/{container_id}"
    params = {"fields": "status_code", "access_token": IG_ACCESS_TOKEN}
    deadline = time.time() + UPLOAD_TIMEOUT

    while time.time() < deadline:
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        status = resp.json().get("status_code", "UNKNOWN")

        print(f"    Container status: {status}")

        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError(
                f"Instagram container {container_id} processing failed (ERROR)"
            )
        # IN_PROGRESS / EXPIRED / PUBLISHED / UNKNOWN → keep waiting
        time.sleep(POLL_INTERVAL)

    raise TimeoutError(
        f"Container {container_id} did not reach FINISHED within {UPLOAD_TIMEOUT}s"
    )


def _publish(container_id: str) -> str:
    """
    Step 4 — Publish the container as a live Reel.
    Returns the Instagram media ID of the published post.
    """
    url = f"{GRAPH_BASE}/{IG_USER_ID}/media_publish"
    params = {"creation_id": container_id, "access_token": IG_ACCESS_TOKEN}
    resp = requests.post(url, params=params, timeout=30)
    resp.raise_for_status()
    media_id = resp.json().get("id")
    if not media_id:
        raise RuntimeError(f"Publish response missing 'id': {resp.json()}")
    return media_id


# ────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────

def post_reel(file_path: str, caption: str) -> str:
    """
    Upload a local MP4 file as an Instagram Reel.

    Args:
        file_path: Absolute path to an MP4 video file.
        caption:   Text caption / hashtags for the post.

    Returns:
        The Instagram media ID of the published Reel.
    """
    if not IG_USER_ID or not IG_ACCESS_TOKEN:
        raise EnvironmentError(
            "IG_USER_ID and IG_ACCESS_TOKEN must be set in .env / environment"
        )

    print("  [1/4] Initialising upload session…")
    session = _init_upload_session(caption)
    container_id = session["id"]
    upload_uri = session["uri"]
    print(f"    Container ID: {container_id}")

    print("  [2/4] Streaming video bytes…")
    _stream_video(upload_uri, file_path)

    print("  [3/4] Waiting for Instagram to process the video…")
    _wait_until_finished(container_id)

    print("  [4/4] Publishing…")
    media_id = _publish(container_id)
    print(f"  ✅ Published! Instagram Media ID: {media_id}")
    return media_id
