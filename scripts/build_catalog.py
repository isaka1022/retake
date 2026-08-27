"""Build the asset catalogue the crew works from.

Merges powerspots' spot text with the curated Wikimedia Commons photos and
their licence metadata, so the rights agent has everything it needs to
attribute each image correctly.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

POWERSPOTS = Path.home() / "projects" / "powerspots" / "scripts"
OUT = Path(__file__).resolve().parent.parent / "retake" / "assets" / "catalog.json"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
THUMB_RE = re.compile(r"/commons/thumb/[0-9a-f]/[0-9a-f]{2}/([^/]+)/")
TAG_RE = re.compile(r"<[^>]*>")


def image_map() -> dict[str, str]:
    src = (POWERSPOTS / "seed-images.mjs").read_text()
    return dict(re.findall(r'"([a-z0-9\-]+)":\s*"(https://upload\.wikimedia\.org/[^"]+)"', src))


def filename_of(thumb_url: str) -> str | None:
    m = THUMB_RE.search(thumb_url)
    return urllib.parse.unquote(m.group(1)) if m else None


def fetch_credits(filenames: list[str]) -> dict[str, dict]:
    """Batch-query Commons for licence metadata (max 50 titles per call)."""
    out: dict[str, dict] = {}
    for i in range(0, len(filenames), 50):
        batch = filenames[i : i + 50]
        params = {
            "action": "query",
            "titles": "|".join(f"File:{f}" for f in batch),
            "prop": "imageinfo",
            "iiprop": "extmetadata",
            "format": "json",
        }
        url = f"{COMMONS_API}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "retake-hackathon/0.1"})
        with urllib.request.urlopen(req, timeout=30) as r:
            pages = json.load(r).get("query", {}).get("pages", {})
        for page in pages.values():
            if "missing" in page:
                continue
            meta = (page.get("imageinfo") or [{}])[0].get("extmetadata")
            if not meta:
                continue
            # MediaWiki normalises underscores to spaces in returned titles.
            title = page.get("title", "").removeprefix("File:").replace(" ", "_")
            out[title] = {
                "artist": TAG_RE.sub("", meta.get("Artist", {}).get("value", "Unknown")).strip(),
                "license": meta.get("LicenseShortName", {}).get("value", "Unknown"),
                "license_url": meta.get("LicenseUrl", {}).get("value", ""),
            }
    return out


def main() -> int:
    spots = json.loads((POWERSPOTS / "data" / "spots.json").read_text())
    imgs = image_map()

    wanted = {}
    for s in spots:
        url = imgs.get(s["slug"])
        if url and (fn := filename_of(url)):
            wanted[s["slug"]] = (url, fn)

    credits = fetch_credits(sorted({fn for _, fn in wanted.values()}))

    catalog = []
    for s in spots:
        if s["slug"] not in wanted:
            continue
        url, fn = wanted[s["slug"]]
        c = credits.get(fn)
        catalog.append({
            "slug": s["slug"],
            "name": s["name"],
            "area": s.get("area", {}).get("prefecture", ""),
            "legend": (s.get("sacred_details") or {}).get("legend", ""),
            "overview": (s.get("contents") or {}).get("overview", ""),
            "highlights": (s.get("contents") or {}).get("highlights", ""),
            "image": {
                "url": url,
                "filename": fn,
                # Missing credit data is kept as null so the rights agent can
                # reject the shot rather than silently publishing it.
                "artist": c["artist"] if c else None,
                "license": c["license"] if c else None,
                "license_url": c["license_url"] if c else None,
            },
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(catalog, ensure_ascii=False, indent=2))
    ok = sum(1 for e in catalog if e["image"]["license"])
    print(f"wrote {OUT} — {len(catalog)} spots, {ok} with licence metadata")
    return 0


if __name__ == "__main__":
    sys.exit(main())
