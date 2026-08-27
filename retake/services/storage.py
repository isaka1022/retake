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
from pathlib import Path

BUCKET = os.environ.get("RETAKE_BUCKET")
PREFIX = "artifacts"

# Rendering happens here; only finished deliverables are published.
SCRATCH = Path(os.environ.get("RETAKE_SCRATCH", "/tmp/retake"))


def scratch_dir(name: str) -> Path:
    d = SCRATCH / name
    d.mkdir(parents=True, exist_ok=True)
    return d


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


def _download(key: str) -> bytes | None:
    blob = _client().bucket(BUCKET).blob(f"{PREFIX}/{key}")
    return blob.download_as_bytes() if blob.exists() else None


async def fetch(key: str) -> bytes | None:
    """Read back a published artifact. Returns None when it is not there."""
    if BUCKET:
        return await asyncio.to_thread(_download, key)
    src = _LOCAL_STORE / key
    if not src.is_file():
        return None
    return await asyncio.to_thread(src.read_bytes)
