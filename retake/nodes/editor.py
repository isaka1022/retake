"""編集 — assembles the cuts and hands the reel back."""

from __future__ import annotations

from pathlib import Path

from google.adk import Context
from google.adk.workflow import node
from google.genai import types

from ..services import ffmpeg_ops, storage


@node
async def editor(ctx: Context) -> dict:
    cuts = ctx.state.get("cuts") or []
    if not cuts:
        raise RuntimeError("編集する素材がありません（撮影が全滅しています）")

    cuts = sorted(cuts, key=lambda c: c["index"])
    take = ctx.state.get("take", 1)
    workdir = storage.scratch_dir(f"{ctx.invocation_id}")
    reel = workdir / f"reel_t{take}.mp4"
    await ffmpeg_ops.concat([c["clip"] for c in cuts], reel)

    # The previous take is published and reviewed; keeping it only costs space.
    for stale in ctx.state.get("stale_files", []):
        storage.discard(stale)
    ctx.state["stale_files"] = [str(reel), str(workdir / f"preview_t{take}.mp4")]
    ctx.state["master_path"] = str(reel)

    seconds = await ffmpeg_ops.duration(reel)
    key = f"{ctx.invocation_id}/reel_t{take}.mp4"
    url = await storage.publish(reel, key)

    # The master is far too heavy to ride inside a session, so the screening
    # room gets a proxy — the same split a real edit suite makes.
    preview = await ffmpeg_ops.proxy(reel, workdir / f"preview_t{take}.mp4")
    ctx.state["preview_path"] = str(preview)
    await ctx.save_artifact(
        "preview.mp4",
        types.Part(
            inline_data=types.Blob(
                data=Path(preview).read_bytes(), mime_type="video/mp4"
            )
        ),
    )

    delivery = {
        "take": take,
        "url": url,
        "seconds": round(seconds, 2),
        "cuts": len(cuts),
        "title": ctx.state.get("plan", {}).get("title", ""),
    }
    ctx.state["delivery"] = delivery
    return delivery
