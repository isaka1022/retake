"""Delivery — the only step that reaches outside the building.

Nothing arrives here without a person having watched the reel and said yes.
The credits the rights node worked out travel with it, since that is where the
attribution actually has to appear.
"""

from __future__ import annotations

import os

from google.adk import Context
from google.adk.workflow import node

from ..services import youtube

# Set on deploy so the finished film is reachable by whoever is handed the run.
PUBLIC_URL = os.environ.get("RETAKE_PUBLIC_URL", "").rstrip("/")


def _description(ctx: Context) -> str:
    plan = ctx.state.get("plan", {})
    lines = [plan.get("theme", ""), ""]

    credits = [c for c in ctx.state.get("clearances", []) if c.get("credit")]
    if credits:
        lines.append("Photo credits")
        lines += [f"  {c['spot']}: {c['credit']}" for c in credits]
        lines.append("")

    licence = ctx.state.get("work_licence")
    if licence:
        lines.append(f"This film is licensed under {licence}")

    review = ctx.state.get("review", {})
    lines += [
        "",
        f"Made by an AI film crew (take {review.get('take')}, director's score {review.get('score')}).",
    ]
    return "\n".join(lines).strip()


@node
async def delivery(ctx: Context) -> dict:
    d = ctx.state["delivery"]
    review = ctx.state.get("review", {})

    # The film itself is the deliverable. A channel is somewhere else to put it.
    result = {
        **d,
        "download": f"{PUBLIC_URL}{d['url']}" if PUBLIC_URL else d["url"],
        "licence": ctx.state.get("work_licence"),
        "credits": [c["credit"] for c in ctx.state.get("clearances", []) if c.get("credit")],
        "screening_note": ctx.state.get("screening", {}).get("note", ""),
        "approved_on_take": review.get("take"),
        "score": review.get("score"),
        "director_comment": review.get("comment"),
    }

    if not youtube.configured():
        result |= {"youtube": "Not configured; download only"}
        ctx.state["published"] = result
        return result

    try:
        posted = await youtube.publish(
            ctx.state["master_path"],
            title=d.get("title") or "AI film crew",
            description=_description(ctx),
            tags=["AllThingsAgenticHackathon", "ADK", "Gemini"],
            privacy="unlisted",
        )
        result |= {"youtube": posted["url"], "video_id": posted["video_id"]}
    except Exception as exc:
        # A failed upload must not read as a successful release, but the film
        # is still finished and still downloadable.
        result |= {"youtube": f"Publish failed: {type(exc).__name__}: {exc}"}

    ctx.state["published"] = result
    return result


@node
async def abandoned(ctx: Context) -> dict:
    """The reel was screened and turned down. Nothing leaves the building."""
    return {
        "published": False,
        "reason": ctx.state.get("screening", {}).get("note") or "Publication was declined at screening",
        "reel": ctx.state.get("delivery", {}).get("url"),
    }
