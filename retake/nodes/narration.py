"""Narration — records the voice track.

The read decides how long each shot has to be on screen, so this runs before
the camera rather than beside it.
"""

from __future__ import annotations

import asyncio

from google.adk import Context
from google.adk.workflow import node

from ..services import storage, tts

# Room to breathe either side of the read.
HEAD_ROOM = 0.6
TAIL_ROOM = 0.9
MIN_SHOT = 3.0
MAX_SHOT = 12.0


async def _record(shot: dict, workdir) -> dict:
    pcm = await tts.speak(shot["narration"])
    path = await tts.to_wav(pcm, workdir / f"vo_{shot['index']:02d}.wav")
    return {
        "index": shot["index"],
        "audio": str(path),
        "seconds": round(tts.pcm_seconds(pcm), 2),
    }


@node
async def narration(ctx: Context) -> dict:
    shots = ctx.state["shots"]
    workdir = storage.scratch_dir(f"{ctx.invocation_id}/vo")

    takes = await asyncio.gather(
        *(_record(s, workdir) for s in shots), return_exceptions=True
    )

    voice, silent = [], []
    for shot, r in zip(shots, takes):
        if isinstance(r, Exception):
            # A missing read costs the shot its voice, not its place in the reel.
            silent.append({"index": shot["index"], "reason": str(r)})
        else:
            voice.append(r)

    # The picture now follows the read instead of a guess at reading speed.
    by_index = {v["index"]: v for v in voice}
    for shot in shots:
        v = by_index.get(shot["index"])
        if v:
            shot["seconds"] = min(
                max(v["seconds"] + HEAD_ROOM + TAIL_ROOM, MIN_SHOT), MAX_SHOT
            )

    ctx.state["shots"] = shots
    ctx.state["voice"] = voice
    ctx.state["silent_shots"] = silent
    return {
        "recorded": len(voice),
        "silent": silent,
        "total_seconds": round(sum(s["seconds"] for s in shots), 2),
    }
