"""撮影 — renders every cut. Shots are independent, so they render together."""

from __future__ import annotations

import asyncio

from google.adk import Context
from google.adk.workflow import node

from ..services import assets, catalog, ffmpeg_ops, storage


async def _shoot_one(shot: dict, workdir) -> dict:
    spot = catalog.get(shot["spot_slug"])
    photo = await assets.fetch_photo(spot["image"]["url"], spot["slug"])
    out = workdir / f"cut_{shot['index']:02d}.mp4"
    await ffmpeg_ops.ken_burns(
        photo,
        out,
        seconds=shot["seconds"],
        zoom_to=shot["zoom_to"],
        motion=shot["motion"],
    )
    return {**shot, "clip": str(out), "photo": str(photo)}


@node
async def camera(ctx: Context) -> dict:
    shots = ctx.state["shots"]
    workdir = storage.scratch_dir(f"{ctx.invocation_id}/cuts")
    results = await asyncio.gather(
        *(_shoot_one(s, workdir) for s in shots), return_exceptions=True
    )

    cuts, failed = [], []
    for shot, r in zip(shots, results):
        if isinstance(r, Exception):
            # One unusable location must not sink the whole shoot.
            failed.append({"index": shot["index"], "reason": str(r)})
        else:
            cuts.append(r)

    ctx.state["cuts"] = cuts
    ctx.state["failed_cuts"] = failed
    return {"cuts": len(cuts), "failed": failed}
