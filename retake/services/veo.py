"""Veo shots.

Generation runs image-to-video from the same Wikimedia still the rest of the
reel uses, so the shot stays faithful to the real location while gaining motion
a pan across a photograph cannot produce.
"""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

from google.genai import types

from .ffmpeg_ops import _run
from .gemini import client

MODEL = "veo-3.1-fast-generate-preview"
SECONDS = 8  # Fixed by the model when a reference image is supplied.
RESOLUTION = "720p"
POLL_INTERVAL = 4.0
TIMEOUT = 300.0

# Each generated second is billed, and the director may ask for several takes,
# so an identical request is answered from disk.
CACHE = Path(__file__).resolve().parent.parent / "assets" / "veo"


class VeoError(RuntimeError):
    pass


async def _to_widescreen(photo: Path, out: Path) -> Path:
    """Veo letterboxes a source that is not 16:9 instead of cropping it, which
    reads as a broken shot beside the full-bleed cuts."""
    await _run([
        "-i", str(photo),
        "-vf", "crop='min(iw,ih*16/9)':'min(ih,iw*9/16)'",
        str(out),
    ])
    return out


def _cache_path(photo: Path, prompt: str) -> Path:
    digest = hashlib.sha256(photo.read_bytes() + prompt.encode()).hexdigest()[:16]
    return CACHE / f"{digest}.mp4"


def is_cached(photo: Path | str, prompt: str) -> bool:
    """A cached clip costs nothing to reuse, so the budget should not be charged."""
    return _cache_path(Path(photo), prompt).is_file()


async def shoot(photo: Path | str, prompt: str, out: Path | str) -> Path:
    photo, out = Path(photo), Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    cached = _cache_path(photo, prompt)
    if cached.is_file():
        await asyncio.to_thread(out.write_bytes, cached.read_bytes())
        return out

    framed = await _to_widescreen(photo, out.with_name(f"{out.stem}_16x9.jpg"))

    c = client()
    op = await c.aio.models.generate_videos(
        model=MODEL,
        prompt=prompt,
        image=types.Image(
            image_bytes=await asyncio.to_thread(framed.read_bytes),
            mime_type="image/jpeg",
        ),
        config=types.GenerateVideosConfig(
            duration_seconds=SECONDS,
            resolution=RESOLUTION,
            number_of_videos=1,
            aspect_ratio="16:9",
        ),
    )

    waited = 0.0
    while not op.done:
        if waited > TIMEOUT:
            raise VeoError(f"Veo did not finish within {TIMEOUT:.0f}s")
        await asyncio.sleep(POLL_INTERVAL)
        waited += POLL_INTERVAL
        op = await c.aio.operations.get(op)

    if not (op.response and op.response.generated_videos):
        raise VeoError("Veo returned no video")

    video = op.response.generated_videos[0].video
    data = video.video_bytes
    if not data:
        # The result usually arrives as a file reference rather than inline.
        data = await asyncio.to_thread(c.files.download, file=video)
    if not data:
        raise VeoError("Could not retrieve the video from Veo")

    framed.unlink(missing_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(cached.write_bytes, data)
    await asyncio.to_thread(out.write_bytes, data)
    return out
