"""撮影 — renders cuts. Shots are independent, so they render together.

On a retake only the shots the director named are shot again; the rest of the
reel is already in the can.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from google.adk import Context
from google.adk.workflow import node

from ..services import assets, captions, catalog, ffmpeg_ops, storage


async def _shoot_one(
    shot: dict, workdir: Path, take: int, credit: str | None, voice: str | None
) -> dict:
    spot = catalog.get(shot["spot_slug"])
    photo = await assets.fetch_photo(spot["image"]["url"], spot["slug"])
    stem = f"cut_{shot['index']:02d}_t{take}"
    raw = workdir / f"{stem}_raw.mp4"
    titled = workdir / f"{stem}_titled.mp4"
    out = workdir / f"{stem}.mp4"
    await ffmpeg_ops.ken_burns(
        photo,
        raw,
        seconds=shot["seconds"],
        zoom_to=shot["zoom_to"],
        motion=shot["motion"],
        exposure=shot.get("exposure", 0.0),
        contrast=shot.get("contrast", 1.0),
    )
    await captions.burn(raw, titled, caption=shot["caption"], credit=credit)
    await ffmpeg_ops.mux_audio(titled, voice, out, seconds=shot["seconds"])
    storage.discard(raw, titled)
    return {**shot, "clip": str(out), "photo": str(photo), "take": take}


def _apply_notes(shots: list[dict], notes: list[dict]) -> list[dict]:
    by_index = {n["cut_index"]: n for n in notes}
    reshoot = []
    for s in shots:
        note = by_index.get(s["index"])
        if note:
            reshoot.append(
                {
                    **s,
                    "motion": note["motion"],
                    "zoom_to": min(max(float(note["zoom_to"]), 1.02), 1.40),
                    "seconds": min(max(float(note["seconds"]), 3.0), 12.0),
                    "exposure": min(max(float(note["exposure"]), -0.30), 0.30),
                    "contrast": min(max(float(note["contrast"]), 0.80), 1.30),
                    "note": note["problem"],
                }
            )
    return reshoot


@node
async def camera(ctx: Context) -> dict:
    take = ctx.state.get("take", 1)
    notes = ctx.state.get("retake_notes") or []
    workdir = storage.scratch_dir(f"{ctx.invocation_id}/cuts")

    if notes:
        queue = _apply_notes(ctx.state["shots"], notes)
        keep = {c["index"]: c for c in ctx.state["cuts"]}
    else:
        queue = ctx.state["shots"]
        keep = {}

    # A reshot cut replaces the old one; the old file has no further use.
    storage.discard(*(keep[s["index"]]["clip"] for s in queue if s["index"] in keep))

    clearances = {c["index"]: c for c in ctx.state.get("clearances", [])}
    voices = {v["index"]: v for v in ctx.state.get("voice", [])}
    results = await asyncio.gather(
        *(
            _shoot_one(
                s,
                workdir,
                take,
                (clearances.get(s["index"]) or {}).get("credit"),
                (voices.get(s["index"]) or {}).get("audio"),
            )
            for s in queue
        ),
        return_exceptions=True,
    )

    failed = []
    for shot, r in zip(queue, results):
        if isinstance(r, Exception):
            # One unusable location must not sink the whole shoot.
            failed.append({"index": shot["index"], "reason": str(r)})
        else:
            keep[r["index"]] = r

    cuts = [keep[i] for i in sorted(keep)]
    ctx.state["cuts"] = cuts
    ctx.state["failed_cuts"] = failed
    return {
        "take": take,
        "shot": [s["index"] for s in queue],
        "in_reel": len(cuts),
        "failed": failed,
    }
