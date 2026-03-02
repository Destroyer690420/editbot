"""
downloader.py
Downloads a tweet's video to the local downloads/ folder using yt-dlp.
Returns the absolute path of the downloaded MP4 file.
"""

import os
import json
import yt_dlp

DOWNLOADS_DIR = os.path.join(os.path.dirname(__file__), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)


def _generate_netscape_cookies(twikit_json_path: str, netscape_path: str) -> None:
    """Convert twikit's {name: value} JSON to Netscape cookies.txt for yt-dlp."""
    with open(twikit_json_path, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    lines = [
        "# Netscape HTTP Cookie File",
        "# https://curl.se/docs/http-cookies.html",
        "",
    ]
    for name, value in cookies.items():
        # Domain, subdomains, path, secure, expiry, name, value
        lines.append(f".x.com\tTRUE\t/\tTRUE\t9999999999\t{name}\t{value}")
    with open(netscape_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  Generated cookies.txt from twikit_cookies.json ({len(cookies)} cookies)")


def download_video(tweet_url: str, tweet_id: str) -> str:
    """
    Download the best-quality video from a tweet URL.

    Args:
        tweet_url: Full tweet URL, e.g. https://twitter.com/user/status/123
        tweet_id:  Used to name the output file (avoids collisions).

    Returns:
        Absolute path to the downloaded MP4 file.

    Raises:
        RuntimeError if the download fails or produces no file.
    """
    output_template = os.path.join(DOWNLOADS_DIR, f"{tweet_id}.%(ext)s")
    expected_mp4 = os.path.join(DOWNLOADS_DIR, f"{tweet_id}.mp4")

    cookies_file = os.path.join(os.path.dirname(__file__), "cookies.txt")

    ydl_opts = {
        # Best video + best audio, any container → merged to MP4
        "format": "bestvideo+bestaudio/best",
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
        "socket_timeout": 60,
    }

    # Use cookies for Twitter authentication
    if os.path.exists(cookies_file):
        ydl_opts["cookiefile"] = cookies_file
    else:
        # CI: no cookies.txt — try to generate from twikit_cookies.json
        twikit_json = os.path.join(os.path.dirname(__file__), "twikit_cookies.json")
        if os.path.exists(twikit_json):
            _generate_netscape_cookies(twikit_json, cookies_file)
            ydl_opts["cookiefile"] = cookies_file
        else:
            raise RuntimeError(
                "No cookies found! Place cookies.txt or twikit_cookies.json "
                "in the project folder."
            )

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(tweet_url, download=True)
        if info is None:
            raise RuntimeError(f"yt-dlp returned no info for {tweet_url}")

        # yt-dlp may choose a different extension after merge; try both
        final_path = ydl.prepare_filename(info)
        if not os.path.exists(final_path):
            # Common case: extension forced to .mp4 by merge_output_format
            if os.path.exists(expected_mp4):
                final_path = expected_mp4
            else:
                raise RuntimeError(
                    f"Downloaded file not found at {final_path} or {expected_mp4}"
                )

    return os.path.abspath(final_path)


# ── quick test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    test_url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "https://twitter.com/EditsGoesHard/status/1"
    )
    test_id = "test_tweet"
    print(f"Downloading: {test_url}")
    path = download_video(test_url, test_id)
    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"Saved to: {path}  ({size_mb:.1f} MB)")
