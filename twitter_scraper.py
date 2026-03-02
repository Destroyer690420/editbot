"""
twitter_scraper.py
Fetches all video posts from a target X/Twitter account using twikit.

twikit uses X's internal GraphQL API authenticated with browser cookies.
It needs a twikit_cookies.json file (simple name→value dict) in the
project folder.

To regenerate twikit_cookies.json:
  1. Export cookies from x.com using any browser extension (JSON format)
  2. Save as cookies.txt in this folder
  3. Run: python make_twikit_cookies.py

Returns a list of dicts sorted oldest-first, ready for downloading.
"""

import asyncio
import json
import os
from twikit import Client
from dotenv import load_dotenv

load_dotenv()

TARGET_ACCOUNT = os.getenv("TARGET_TWITTER_ACCOUNT", "EditsGoesHard")
TWIKIT_COOKIES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "twikit_cookies.json")


def _require_cookies() -> None:
    if not os.path.exists(TWIKIT_COOKIES):
        raise FileNotFoundError(
            f"\n\ntwikit_cookies.json not found at {TWIKIT_COOKIES}\n"
            "Run: python make_twikit_cookies.py\n"
            "(Make sure cookies.txt exists first — export from x.com in your browser)\n"
        )


async def _fetch_tweets(limit: int) -> list[dict]:
    """Async core: authenticate with cookies and pull tweet list."""
    _require_cookies()

    client = Client(language="en-US")
    client.load_cookies(TWIKIT_COOKIES)

    # Resolve @username → user object
    user = await client.get_user_by_screen_name(TARGET_ACCOUNT)
    print(f"  Resolved @{TARGET_ACCOUNT} → id={user.id}")

    results = []
    tweets = await user.get_tweets("Tweets", count=min(limit, 40))

    while tweets and len(results) < limit:
        for tweet in tweets:
            # Only keep tweets that have video/gif media
            if not tweet.media:
                continue
            has_video = any(
                m.type in ("video", "animated_gif")
                for m in (tweet.media or [])
            )
            if not has_video:
                continue

            tweet_url = f"https://x.com/{TARGET_ACCOUNT}/status/{tweet.id}"
            caption = (tweet.full_text or "").strip()

            results.append(
                {
                    "tweet_id": str(tweet.id),
                    "tweet_url": tweet_url,
                    "caption": caption,
                    "media_type": "video",
                }
            )

        if len(results) >= limit:
            break
        # Fetch next page
        try:
            tweets = await tweets.next()
        except Exception:
            break

    # Sort oldest-first so we post chronologically
    results.sort(key=lambda x: int(x["tweet_id"]))
    return results


def fetch_media_tweets(limit: int = 200) -> list[dict]:
    """Public sync wrapper."""
    results = asyncio.run(_fetch_tweets(limit))
    print(f"  Found {len(results)} video tweet(s)")
    return results


# ── quick test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tweets = fetch_media_tweets(limit=20)
    print(f"\n{'─'*50}")
    for t in tweets:
        print(f"  [{t['tweet_id']}] {t['tweet_url']}")
        if t["caption"]:
            print(f"     {t['caption'][:80]}")
