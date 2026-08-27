"""Artifact storage.

Cloud Run's filesystem is tmpfs, so anything a crew member renders has to leave
the container to survive. Locally there is no bucket, so the same calls fall
back to disk. Both modes hand back the same `/artifacts/<key>` URL path, which
keeps the nodes free of any environment branching.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from collections.abc import AsyncIterator
from pathlib import Path

BUCKET = os.environ.get("RETAKE_BUCKET")
PREFIX = "artifacts"

# Rendering happens here; only finished deliverables are published.
SCRATCH = Path(os.environ.get("RETAKE_SCRATCH", "/tmp/retake"))


def scratch_dir(name: str) -> Path:
    d = SCRATCH / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def discard(*paths: Path | str) -> None:
    """Drop intermediates once they are no longer referenced. On Cloud Run the
    scratch tree is RAM, so holding every take is a slow memory leak."""
    for p in paths:
        p = Path(p)
        try:
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.exists():
                p.unlink()
        except OSError:
            pass


def clear_run(invocation_id: str) -> None:
    discard(SCRATCH / invocation_id)


_LOCAL_STORE = Path(__file__).resolve().parent.parent.parent / "out" / "published"


def _client():
    from google.cloud import storage

    return storage.Client()


def _upload(path: Path, key: str) -> None:
    _client().bucket(BUCKET).blob(f"{PREFIX}/{key}").upload_from_filename(str(path))


async def publish(path: Path, key: str) -> str:
    """Move a finished file out of scratch and return its stable URL path."""
    if BUCKET:
        await asyncio.to_thread(_upload, path, key)
    else:
        dest = _LOCAL_STORE / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copyfile, path, dest)
    return f"/{PREFIX}/{key}"


# Cloud Run caps a buffered response at 32MB and a master reel runs past that,
# so artifacts are streamed rather than loaded whole.
CHUNK = 1 << 20


def _blob(key: str):
    return _client().bucket(BUCKET).blob(f"{PREFIX}/{key}")


async def size(key: str) -> int | None:
    """Bytes held for this key, or None when nothing is stored under it."""
    if BUCKET:
        blob = await asyncio.to_thread(_blob, key)
        if not await asyncio.to_thread(blob.exists):
            return None
        await asyncio.to_thread(blob.reload)
        return blob.size
    src = _LOCAL_STORE / key
    return src.stat().st_size if src.is_file() else None


async def stream(key: str) -> AsyncIterator[bytes]:
    if BUCKET:
        handle = await asyncio.to_thread(lambda: _blob(key).open("rb"))
    else:
        handle = await asyncio.to_thread((_LOCAL_STORE / key).open, "rb")
    try:
        while True:
            block = await asyncio.to_thread(handle.read, CHUNK)
            if not block:
                return
            yield block
    finally:
        await asyncio.to_thread(handle.close)
