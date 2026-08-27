"""Source photo fetching.

Wikimedia asks clients to identify themselves and to back off politely; both
matter here because the crew fetches the same host repeatedly.
"""

from __future__ import annotations

import asyncio
import time
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "retake-hackathon/0.1 (https://github.com/isaka1022/retake; isaka1022@gmail.com)"
CACHE = Path(__file__).resolve().parent.parent / "assets" / "photos"
_MIN_INTERVAL = 1.0  # seconds between requests to the same host
_last_request = 0.0
_lock = asyncio.Lock()


def _get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


async def fetch_photo(url: str, slug: str, *, attempts: int = 4) -> Path:
    """Download a source photo, caching it so repeated runs stay offline."""
    global _last_request
    dest = CACHE / f"{slug}.jpg"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(attempts):
        async with _lock:
            wait = _MIN_INTERVAL - (time.monotonic() - _last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            _last_request = time.monotonic()
        try:
            data = await asyncio.to_thread(_get, url)
            dest.write_bytes(data)
            return dest
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or attempt == attempts - 1:
                raise
            await asyncio.sleep(2 ** attempt * 2)
    raise RuntimeError(f"unreachable: {slug}")
