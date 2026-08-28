"""Storyboard — assigns concrete camera moves to each cut."""

from __future__ import annotations

from google.adk import Context
from google.adk.workflow import node

from ..services import catalog, gemini

MOTIONS = ["push_in", "pan_left", "pan_right"]

SYSTEM = """You are the storyboard artist for a short film.
You assign camera work to each cut. Do not let the same motion repeat three times in a row.

There are two ways to build a cut:
- still: apply camera work to a still photo. Reliable and fast.
- veo: generate video from a still photo. Water and trees actually move, but generation
  takes about 50 seconds and costs money.

Use veo for at most one cut — whichever one motion helps the most. Never use it on a
subject with nothing to move."""

SCHEMA = {
    "type": "object",
    "properties": {
        "shots": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "spot_slug": {"type": "string"},
                    "seconds": {"type": "number"},
                    "motion": {"type": "string", "enum": MOTIONS},
                    "zoom_to": {"type": "number"},
                    "caption": {
                        "type": "string",
                        "description": (
                            "On-screen caption, in English, 34 characters or fewer so "
                            "it fits a 1920px-wide frame without wrapping."
                        ),
                    },
                    "source": {"type": "string", "enum": ["still", "veo"]},
                    "motion_prompt": {"type": "string"},
                },
                "required": [
                    "spot_slug", "seconds", "motion", "zoom_to", "caption",
                    "source", "motion_prompt",
                ],
            },
        }
    },
    "required": ["shots"],
}


@node
async def storyboard(ctx: Context) -> dict:
    plan = ctx.state["plan"]
    lines = "\n".join(
        f"{i}. {catalog.get(c['spot_slug'])['name']} / narration: \"{c['narration']}\""
        f" / intent: {c['visual_intent']}"
        for i, c in enumerate(plan["cuts"])
    )
    board = await gemini.structured(
        f"Film title: \"{plan['title']}\"\n\nCuts:\n{lines}\n\n"
        "For each cut, assign seconds (4-10), motion, zoom_to (1.05-1.30), "
        "an on-screen caption (English, 34 characters or fewer), source, and, "
        "when source is veo, a motion_prompt describing what moves and how. "
        "For still cuts, motion_prompt can be an empty string.",
        SCHEMA,
        system=SYSTEM,
    )
    shots = []
    for i, s in enumerate(board["shots"][: len(plan["cuts"])]):
        spot = catalog.get(s["spot_slug"]) or catalog.get(plan["cuts"][i]["spot_slug"])
        shots.append(
            {
                "index": i,
                "spot_slug": spot["slug"],
                "seconds": min(max(float(s["seconds"]), 3.0), 12.0),
                "motion": s["motion"] if s["motion"] in MOTIONS else "push_in",
                "zoom_to": min(max(float(s["zoom_to"]), 1.02), 1.4),
                "caption": s["caption"],
                "narration": plan["cuts"][i]["narration"],
                "source": s["source"],
                "motion_prompt": s.get("motion_prompt", ""),
            }
        )

    # Generation is billed per second and the director may call for several
    # takes, so only the strongest candidate is generated.
    generated = [s for s in shots if s["source"] == "veo"]
    for extra in generated[1:]:
        extra["source"] = "still"
    ctx.state["shots"] = shots
    return {"shots": shots}
