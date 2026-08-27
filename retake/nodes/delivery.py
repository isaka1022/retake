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
        "approved_on_take": review.get("take"),
        "score": review.get("score"),
        "director_comment": review.get("comment"),
    }
