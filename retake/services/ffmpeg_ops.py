"""ffmpeg operations. Deliberately knows nothing about ADK.

The Ken Burns recipe and the pitfalls it avoids come from the travel-doc-video
skill's ffmpeg reference, which records what actually broke across five real
productions.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"

FPS = 25
SIZE = "1920x1080"
# zoompan rounds fractionally and produces a 1px jitter unless the source is
# upscaled well beyond the output first.
OVERSAMPLE_WIDTH = 8000


class FfmpegError(RuntimeError):
    pass


async def _run(args: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise FfmpegError(err.decode()[-1500:])


def _zoompan_expr(frames: int, zoom_to: float, motion: str) -> str:
    """Ease-in-out zoom. Linear motion is the biggest tell of amateur work."""
    span = zoom_to - 1.0
    z = f"1+{span:.4f}*(1-cos(3.14159265*on/{frames}))/2"
    if motion == "pan_right":
        x, y = f"(iw-iw/zoom)*on/{frames}", "ih/2-(ih/zoom/2)"
        z = f"{zoom_to:.4f}"
    elif motion == "pan_left":
        x, y = f"(iw-iw/zoom)*(1-on/{frames})", "ih/2-(ih/zoom/2)"
        z = f"{zoom_to:.4f}"
    else:  # push_in
        x, y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    return (
        f"scale={OVERSAMPLE_WIDTH}:-1,"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={SIZE}:fps={FPS}"
    )


async def ken_burns(
    image: Path | str,
    out: Path | str,
    *,
    seconds: float,
    zoom_to: float = 1.15,
    motion: str = "push_in",
) -> Path:
    """Render one still into a moving clip.

    Uses an explicit frame count rather than -shortest: combining `-loop 1`
    with zoompan and `-shortest` inflates the output by roughly 1.6x.
    """
    frames = max(1, round(seconds * FPS))
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    await _run([
        "-loop", "1", "-i", str(image),
        "-filter_complex", f"[0:v]{_zoompan_expr(frames, zoom_to, motion)}[v]",
        "-map", "[v]", "-frames:v", str(frames),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(FPS), str(out),
    ])
    return out


async def concat(clips: list[Path | str], out: Path | str) -> Path:
    """Join clips losslessly via the concat demuxer."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    listing = out.with_suffix(".txt")
    listing.write_text("".join(f"file '{Path(c).resolve()}'\n" for c in clips))
    await _run([
        "-f", "concat", "-safe", "0", "-i", str(listing),
        "-c", "copy", str(out),
    ])
    listing.unlink(missing_ok=True)
    return out


async def duration(path: Path | str) -> float:
    proc = await asyncio.create_subprocess_exec(
        FFPROBE, "-v", "error", "-show_entries", "format=duration",
        "-of", "csv=p=0", str(path),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    out, _ = await proc.communicate()
    return float(out.decode().strip())
