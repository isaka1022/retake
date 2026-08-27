"""配信 — the end of the line. Publishing to YouTube lands here later."""

from __future__ import annotations

from google.adk import Context
from google.adk.workflow import node


@node
async def delivery(ctx: Context) -> dict:
    d = ctx.state["delivery"]
    review = ctx.state.get("review", {})
    return {
        **d,
        "published": True,
        "screening_note": ctx.state.get("screening", {}).get("note", ""),
        "approved_on_take": review.get("take"),
        "score": review.get("score"),
        "director_comment": review.get("comment"),
    }


@node
async def abandoned(ctx: Context) -> dict:
    """The reel was screened and turned down. Nothing leaves the building."""
    return {
        "published": False,
        "reason": ctx.state.get("screening", {}).get("note") or "試写で公開が見送られました",
        "reel": ctx.state.get("delivery", {}).get("url"),
    }
