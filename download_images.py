#!/usr/bin/env python3
"""
Download every post image listed inside index.html and save it as
images/<shortcode>.<ext>  (the exact name the website looks for).

How to use
----------
1. Put this file in the SAME folder as index.html.
2. Open a terminal / command prompt in that folder.
3. Run:   python download_images.py        (or  python3 download_images.py)

It is safe to stop and run again: files that were already downloaded are skipped.
Anything that fails is written to failed.txt so you can see what is missing.
Needs only Python 3.8+ (no extra installs).
"""

import re
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML = HERE / "index.html"
OUT = HERE / "images"
WORKERS = 4          # downloads at the same time (keep low to be polite)
RETRIES = 3
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
}

# ["shortcode","p|r","photo|carousel|clip|video",pinned,"ext","https://...thumb..."]
ENTRY = re.compile(
    r'\["([A-Za-z0-9_-]{8,})","([pr])","(\w+)",(\d),"(\w+)","(https?://[^"]+)"\]'
)


def load_entries():
    if not HTML.exists():
        sys.exit("index.html not found. Put this script in the same folder as index.html.")
    text = HTML.read_text(encoding="utf-8")
    entries = []
    for code, _kind, _media, _pin, ext, url in ENTRY.findall(text):
        url = url.replace("\\/", "/").replace("\\u0026", "&").replace("&amp;", "&")
        entries.append((code, ext, url))
    return entries


def download(code, ext, url):
    dest = OUT / f"{code}.{ext}"
    if dest.exists() and dest.stat().st_size > 1000:
        return code, "skipped", ""
    last_err = ""
    for attempt in range(1, RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                ctype = r.headers.get("Content-Type", "")
            if len(data) < 1000 or not ctype.startswith("image"):
                raise ValueError(f"not an image ({ctype}, {len(data)} bytes)")
            tmp = dest.with_suffix(dest.suffix + ".part")
            tmp.write_bytes(data)
            tmp.replace(dest)
            return code, "ok", ""
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code in (403, 404, 410):   # link expired / not allowed: retrying won't help
                break
        except Exception as e:              # network hiccup etc.
            last_err = str(e)
        time.sleep(1.5 * attempt)
    return code, "failed", last_err


def main():
    OUT.mkdir(exist_ok=True)
    entries = load_entries()
    if not entries:
        sys.exit("No posts found inside index.html.")
    print(f"Found {len(entries)} posts. Saving into: {OUT}")

    counts = {"ok": 0, "skipped": 0, "failed": 0}
    failed = []
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(download, *e) for e in entries]
        for f in as_completed(futures):
            code, status, err = f.result()
            counts[status] += 1
            done += 1
            if status == "failed":
                failed.append(f"{code}\t{err}")
            if done % 25 == 0 or done == len(entries):
                print(f"  {done}/{len(entries)}  "
                      f"downloaded {counts['ok']}, already had {counts['skipped']}, failed {counts['failed']}")

    if failed:
        (HERE / "failed.txt").write_text("\n".join(failed) + "\n", encoding="utf-8")
        print(f"\n{len(failed)} could not be downloaded. See failed.txt")
        print("If they say HTTP 403/410, the Instagram links have expired: re-run your scraper for fresh links.")
    else:
        failed_file = HERE / "failed.txt"
        if failed_file.exists():
            failed_file.unlink()
        print("\nAll images are saved. You can now upload the images folder to GitHub.")


if __name__ == "__main__":
    main()
