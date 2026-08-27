"""Caption and credit-card burn-in. Deliberately knows nothing about ADK."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from retake.services.ffmpeg_ops import FPS, SIZE, FfmpegError, _run

# Verified paths only (fc-list on each platform), not guesses.
_FONT_CANDIDATES = [
    # Debian container: apt-get install fonts-noto-cjk (see Dockerfile).
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
    # macOS, where a user-installed Noto Sans JP is the usual case.
    Path.home() / "Library/Fonts/NotoSansJP-VariableFont_wght.ttf",
    Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
]


class FontNotFoundError(RuntimeError):
    pass


def _font_path() -> str:
    for candidate in _FONT_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
    raise FontNotFoundError(
        "No Noto Sans CJK font found. Install fonts-noto-cjk (Debian) "
        "or place a Noto Sans JP/CJK font under one of: "
        f"{_FONT_CANDIDATES}"
    )


def _drawtext(text: str, font: str, *, size: int, y: str, box: bool) -> tuple[str, Path]:
    # textfile= avoids drawtext's text= escaping rules for `:`, `'`, `\`, `%`,
    # which Japanese punctuation and dashes routinely collide with.
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    tmp.write(text)
    tmp.close()
    box_args = ":box=1:boxcolor=black@0.45:boxborderw=12" if box else ""
    expr = (
        f"drawtext=fontfile='{font}':textfile='{tmp.name}':"
        f"fontsize={size}:fontcolor=white:borderw=2:bordercolor=black@0.8:"
        f"x=(w-text_w)/2:y={y}{box_args}"
    )
    return expr, Path(tmp.name)


async def burn(
    src: Path | str,
    out: Path | str,
    *,
    caption: str,
    credit: str | None = None,
) -> Path:
    """Burn a bottom caption and optional small credit line into a clip."""
    font = _font_path()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)

    filters = []
    tmpfiles: list[Path] = []
    caption_expr, caption_file = _drawtext(
        caption, font, size=48, y="h-140", box=True
    )
    filters.append(caption_expr)
    tmpfiles.append(caption_file)
    if credit:
        credit_expr, credit_file = _drawtext(
            credit, font, size=22, y="h-48", box=False
        )
        credit_expr = credit_expr.replace(
            "x=(w-text_w)/2", "x=w-text_w-24"
        )
        filters.append(credit_expr)
        tmpfiles.append(credit_file)

    try:
        await _run([
            "-i", str(src),
            "-vf", ",".join(filters),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "copy",
            str(out),
        ])
    finally:
        for f in tmpfiles:
            f.unlink(missing_ok=True)
    return out


async def credits_card(
    out: Path | str,
    *,
    lines: list[str],
    seconds: float = 4.0,
) -> Path:
    """Render a black end card with the given credit lines centered."""
    font = _font_path()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    frames = max(1, round(seconds * FPS))

    # Fewer lines can afford bigger type; cap so many lines still fit 1080p.
    size = max(24, min(48, 640 // max(1, len(lines))))
    line_height = int(size * 1.6)
    text = "\n".join(lines)

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    )
    tmp.write(text)
    tmp.close()

    try:
        await _run([
            "-f", "lavfi", "-i", f"color=c=black:s={SIZE}:r={FPS}:d={seconds}",
            "-vf", (
                f"drawtext=fontfile='{font}':textfile='{tmp.name}':"
                f"fontsize={size}:fontcolor=white:line_spacing={line_height - size}:"
                f"x=(w-text_w)/2:y=(h-text_h)/2"
            ),
            "-frames:v", str(frames),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            str(out),
        ])
    finally:
        Path(tmp.name).unlink(missing_ok=True)
    return out
