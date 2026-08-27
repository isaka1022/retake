"""Narration. Gemini returns raw PCM, which ffmpeg needs to be told about."""

from __future__ import annotations

import asyncio
from pathlib import Path

from google.genai import types

from .ffmpeg_ops import _run
from .gemini import client

MODEL = "gemini-3.1-flash-tts-preview"
VOICE = "Kore"

# The API hands back headerless little-endian 16-bit mono at this rate.
SAMPLE_RATE = 24000
BYTES_PER_SAMPLE = 2


async def speak(text: str, *, voice: str = VOICE) -> bytes:
    resp = await client().aio.models.generate_content(
        model=MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    )
    return resp.candidates[0].content.parts[0].inline_data.data


def pcm_seconds(pcm: bytes) -> float:
    return len(pcm) / (SAMPLE_RATE * BYTES_PER_SAMPLE)


async def to_wav(pcm: bytes, out: Path | str) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = out.with_suffix(".pcm")
    await asyncio.to_thread(raw.write_bytes, pcm)
    await _run([
        "-f", "s16le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-i", str(raw),
        "-c:a", "pcm_s16le", str(out),
    ])
    raw.unlink(missing_ok=True)
    return out
