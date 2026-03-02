"""
make_twikit_cookies.py  —  run once to generate twikit_cookies.json
Reads cookies.txt (Netscape format) and outputs a simple {name: value}
JSON file that twikit's set_cookies() / load_cookies() can read.
"""

import re
import json
import os

NETSCAPE = os.path.join(os.path.dirname(__file__), "cookies.txt")
OUT = os.path.join(os.path.dirname(__file__), "twikit_cookies.json")

cookies = {}
with open(NETSCAPE, "r", encoding="utf-8") as f:
    for line in f:
        line = line.rstrip("\n")
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            name = parts[5]
            value = parts[6]
            cookies[name] = value

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(cookies, f, indent=2)

print(f"Written {OUT} with {len(cookies)} cookies")
print(f"  auth_token : {cookies.get('auth_token', 'MISSING')[:20]}...")
print(f"  ct0        : {cookies.get('ct0', 'MISSING')[:20]}...")
