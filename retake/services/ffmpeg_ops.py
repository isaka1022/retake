"""ffmpeg operations. Deliberately knows nothing about ADK.

The Ken Burns recipe and the pitfalls it avoids come from the travel-doc-video
skill's ffmpeg reference, which records what actually broke across five real
productions.
"""

from __future__ import annotations

import asyncio
import json
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
    exposure: float = 0.0,
    contrast: float = 1.0,
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
        "-filter_complex",
        f"[0:v]{_zoompan_expr(frames, zoom_to, motion)}"
        f",eq=brightness={exposure:.3f}:contrast={contrast:.3f}[v]",
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


async def proxy(src: Path | str, out: Path | str) -> Path:
    """A small viewing copy. The master stays in the bucket; only this is light
    enough to ride along inside a session for the human to watch."""
    out = Path(out)
    await _run([
        "-i", str(src),
        "-vf", "scale=960:-2",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(out),
    ])
    return out


# Every cut carries the same audio layout so the concat demuxer can join them
# without re-encoding.
AUDIO_RATE = 48000
AUDIO_CHANNELS = 2


async def mux_audio(
    video: Path | str,
    audio: Path | str | None,
    out: Path | str,
    *,
    seconds: float,
    lead_in: float = 0.6,
) -> Path:
    """Lay the read over the picture, padded to the length of the shot.

    A shot with no read still gets a silent track: a cut missing audio entirely
    would desync everything after it once the clips are joined.
    """
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    silence = f"anullsrc=r={AUDIO_RATE}:cl=stereo"

    if audio is None:
        args = [
            "-i", str(video), "-f", "lavfi", "-i", silence,
            "-map", "0:v", "-map", "1:a",
        ]
    else:
        args = [
            "-i", str(video), "-i", str(audio),
            "-filter_complex",
            f"[1:a]adelay={int(lead_in * 1000)}:all=1,"
            f"aformat=sample_rates={AUDIO_RATE}:channel_layouts=stereo,"
            f"apad[a]",
            "-map", "0:v", "-map", "[a]",
        ]

    await _run([
        *args,
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-ar", str(AUDIO_RATE), "-ac", str(AUDIO_CHANNELS),
        "-t", f"{seconds:.3f}",
        str(out),
    ])
    return out


async def normalise(
    src: Path | str,
    out: Path | str,
    *,
    seconds: float,
    exposure: float = 0.0,
    contrast: float = 1.0,
) -> Path:
    """Bring a generated clip in line with the rest of the reel.

    Veo returns 720p with its own audio at a fixed length; the concat demuxer
    needs every cut to match, so this resizes, drops the audio and either trims
    or freezes the tail to the length the edit asked for.
    """
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    width, height = SIZE.split("x")
    await _run([
        "-i", str(src),
        "-vf",
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"eq=brightness={exposure:.3f}:contrast={contrast:.3f},"
        f"tpad=stop_mode=clone:stop_duration={max(seconds, 0.1):.3f},"
        f"fps={FPS}",
        "-an",
        "-frames:v", str(max(1, round(seconds * FPS))),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        str(out),
    ])
    return out


# YouTube plays back at this level; anything quieter just sounds thin next to
# everything else on the platform.
TARGET_LUFS = -14.0


async def _measure_loudness(src: Path) -> dict[str, str] | None:
    """First pass. Returns None when the track is silent or unmeasurable."""
    proc = await asyncio.create_subprocess_exec(
        FFMPEG, "-hide_banner", "-i", str(src),
        "-af", f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    text = err.decode()
    start = text.rfind("{")
    if proc.returncode != 0 or start == -1:
        return None
    try:
        # ffmpeg keeps logging after the report, so the object has to be read
        # out of the stream rather than parsed as the whole remainder.
        measured, _ = json.JSONDecoder().raw_decode(text[start:])
        return measured
    except json.JSONDecodeError:
        return None


async def normalise_loudness(src: Path | str, out: Path | str) -> tuple[Path, bool]:
    """Two-pass loudness.

    Falls back to a copy rather than failing the edit, and says which happened:
    a silent fallback here looks exactly like a working normalisation.
    """
    src, out = Path(src), Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    measured = await _measure_loudness(src)
    if not measured:
        await _run(["-i", str(src), "-c", "copy", str(out)])
        return out, False

    await _run([
        "-i", str(src),
        "-af",
        f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11:"
        f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']}:linear=true",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-ar", str(AUDIO_RATE), "-ac", str(AUDIO_CHANNELS),
        str(out),
    ])
    return out, True
