"""
main.py
Orchestrator: scrapes Twitter → downloads video → uploads to Instagram.
Run once per scheduled invocation (GitHub Actions posts 1 video per run).
"""

import os
import sys
import re
import logging
from dotenv import load_dotenv

load_dotenv()

# ── Config ───────────────────────────────────────────────────────────────────
MAX_POSTS = int(os.getenv("MAX_POSTS_PER_RUN", "1"))
DEFAULT_CAPTION = os.getenv("DEFAULT_CAPTION", "#edits #viral #fyp #trending #videoedits")
DRY_RUN = os.getenv("DRY_RUN", "false").strip().lower() == "true"
PROCESSED_FILE = os.path.join(os.path.dirname(__file__), "processed_ids.txt")

URL_RE = re.compile(r'https?://\S+')

def _build_caption(tweet_text: str) -> str:
    """Strip URLs from tweet text; append default hashtags. Return clean caption."""
    # Remove all URLs (t.co links etc.)
    clean = URL_RE.sub("", tweet_text).strip()
    # Combine cleaned text + hashtags (avoid duplicates)
    parts = [p for p in [clean, DEFAULT_CAPTION] if p]
    return "\n\n".join(parts) if clean else DEFAULT_CAPTION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Imports from local modules ────────────────────────────────────────────────
from twitter_scraper import fetch_media_tweets
from downloader import download_video
from uploader import post_reel


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_processed() -> set[str]:
    """Return the set of tweet IDs already posted to Instagram."""
    if not os.path.exists(PROCESSED_FILE):
        return set()
    with open(PROCESSED_FILE, "r", encoding="utf-8") as fh:
        return {line.strip() for line in fh if line.strip()}


def mark_processed(tweet_id: str) -> None:
    """Append a tweet ID to processed_ids.txt."""
    with open(PROCESSED_FILE, "a", encoding="utf-8") as fh:
        fh.write(tweet_id + "\n")


def safe_delete(path: str) -> None:
    """Delete a file silently (best-effort cleanup)."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    mode_label = "[DRY RUN] " if DRY_RUN else ""
    log.info(f"🤖 Twitter→Instagram Bot starting {mode_label}")

    # 1. Fetch all video tweets from the target account
    log.info("🔍 Fetching media tweets from Twitter…")
    try:
        all_tweets = fetch_media_tweets(limit=500)
    except Exception as exc:
        log.error(f"❌ Could not fetch tweets: {exc}")
        sys.exit(1)

    log.info(f"   Found {len(all_tweets)} video tweet(s) total")

    # 2. Filter out already-processed tweet IDs
    processed = load_processed()
    new_tweets = [t for t in all_tweets if t["tweet_id"] not in processed]
    log.info(f"   {len(new_tweets)} new / unposted tweet(s)")

    if not new_tweets:
        log.info("✅ Nothing new to post. Done.")
        return

    # 3. Post up to MAX_POSTS tweets (oldest first)
    posted = 0
    for tweet in new_tweets:
        if posted >= MAX_POSTS:
            log.info(f"ℹ️  Reached limit of {MAX_POSTS} post(s) for this run.")
            break

        tweet_id = tweet["tweet_id"]
        tweet_url = tweet["tweet_url"]
        caption = _build_caption(tweet["caption"])

        log.info(f"\n📥 Tweet {tweet_id}")
        log.info(f"   URL     : {tweet_url}")
        log.info(f"   Caption : {caption[:80]}{'…' if len(caption) > 80 else ''}")

        # 3a. Download
        local_file = None
        try:
            log.info("   ⬇  Downloading video…")
            local_file = download_video(tweet_url, tweet_id)
            size_mb = os.path.getsize(local_file) / (1024 * 1024)
            log.info(f"   ✔  Downloaded: {local_file}  ({size_mb:.1f} MB)")
        except Exception as exc:
            log.error(f"   ❌ Download failed — skipping: {exc}")
            safe_delete(local_file)
            continue

        # 3b. Upload / publish
        if DRY_RUN:
            log.info(f"   {mode_label}Would upload {local_file} and post to Instagram.")
            mark_processed(tweet_id)
            safe_delete(local_file)
            posted += 1
            continue

        try:
            log.info("   📤 Uploading to Instagram…")
            post_reel(local_file, caption)
            mark_processed(tweet_id)
            posted += 1
        except Exception as exc:
            log.error(f"   ❌ Instagram upload failed — skipping: {exc}")
        finally:
            safe_delete(local_file)

    log.info(f"\n✅ Done. Posted {posted} / {MAX_POSTS} video(s) this run.")


if __name__ == "__main__":
    main()
