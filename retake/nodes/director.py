"""Director — watches the cut and decides whether it ships.

The review is a real one: the reel is handed to Gemini as video, not described
to it. Every note carries the full replacement setup, so a retake is always
something the crew can actually execute — a note the camera cannot act on would
loop forever without improving the reel.
"""

from __future__ import annotations

from pathlib import Path

from google.adk import Context
from google.adk.workflow import node

from ..services import gemini

QUALITY_BAR = 70
MAX_TAKES = 3

SYSTEM = """You are the director of a short film. You do not compromise, and you are specific.
All you have to work with is camera work and exposure adjustment applied to a single
still photo. Every retake instruction must stay within those two levers — never write a
request the crew cannot execute.

You remember the notes you gave last time. On a retake pass, do not start the critique
from scratch: judge whether the previous notes were addressed and whether the cut
improved. If the material has hit its limit and cannot get any better, ship it even if
it is not perfect. Repeating the same note three times means either the instruction was
wrong or the material has hit its limit.

Write comment and every note's problem in English, in concrete terms a crew member could
act on."""

NOTE = {
    "type": "object",
    "properties": {
        "cut_index": {"type": "integer"},
        "problem": {
            "type": "string",
            "description": (
                "A concrete, specific problem with this cut, in English, that a crew "
                "member could act on — not a vague or generic remark."
            ),
        },
        "motion": {"type": "string", "enum": ["push_in", "pan_left", "pan_right"]},
        "zoom_to": {"type": "number"},
        "seconds": {"type": "number"},
        "exposure": {"type": "number"},
        "contrast": {"type": "number"},
    },
    "required": [
        "cut_index", "problem", "motion", "zoom_to", "seconds", "exposure", "contrast",
    ],
}

SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer"},
        "decision": {"type": "string", "enum": ["ship", "retake"]},
        "comment": {
            "type": "string",
            "description": (
                "The director's overall verdict, in English, specific enough that a "
                "judge reading it understands exactly what worked and what did not."
            ),
        },
        "notes": {"type": "array", "items": NOTE},
    },
    "required": ["score", "decision", "comment", "notes"],
}

PROMPT = """Review this cut. The shot breakdown and current settings are below.

{sheet}
{missing}{history}
Score it out of 100, and give your decision (ship or retake) in decision.
If retake, issue instructions for the cuts that need fixing. Every instruction must
include all of the following:
- motion: camera move
- zoom_to: how tight the push is, 1.02-1.40
- seconds: duration, 3-12
- exposure: brightness correction, -0.30 to 0.30 (use a negative value to pull back a
  blown-out highlight)
- contrast: contrast, 0.80-1.30

If there is nothing wrong, leave notes empty."""


def _history(log: list[dict]) -> str:
    """What the director already asked for. Without it each review starts from
    scratch and the loop never converges."""
    if not log:
        return ""
    lines = ["\nYour previous decisions:"]
    for r in log:
        asked = ", ".join(
            f"cut {n['cut_index']} ({n['problem']})" for n in r.get("issued", [])
        )
        lines.append(f"  take {r['take']}: {r['score']} — {r['comment']}")
        if asked:
            lines.append(f"    instructions given: {asked}")
    lines.append("Judge how these were addressed in this pass.")
    return "\n".join(lines) + "\n"


def _shot_sheet(cuts: list[dict]) -> str:
    lines, at = [], 0.0
    for c in sorted(cuts, key=lambda x: x["index"]):
        if c.get("source") == "veo":
            # A generated shot cannot be recomposed without paying to make it
            # again, so only the grade is on the table.
            lines.append(
                f"cut {c['index']}: {at:.1f}-{at + c['seconds']:.1f}s / generated shot"
                f" (camera work is fixed, exposure only) / "
                f"exposure {c.get('exposure', 0.0):+.2f} / "
                f"contrast {c.get('contrast', 1.0):.2f}"
            )
        else:
            lines.append(
                f"cut {c['index']}: {at:.1f}-{at + c['seconds']:.1f}s / {c['motion']} / "
                f"zoom {c['zoom_to']:.2f} / exposure {c.get('exposure', 0.0):+.2f} / "
                f"contrast {c.get('contrast', 1.0):.2f}"
            )
        at += c["seconds"]
    return "\n".join(lines)


@node
async def director(ctx: Context) -> dict:
    take = ctx.state.get("take", 1)
    cuts = ctx.state["cuts"]

    # Judging the assembly without knowing a location never made it would
    # sign off on a film that is missing its subject.
    lost = ctx.state.get("failed_cuts") or []
    missing = (
        "\nCuts that could not be shot: "
        + ", ".join(f"cut {f['index']} ({f.get('spot', '')})" for f in lost)
        + ". These are missing from the edit as-is.\n"
        if lost
        else ""
    )

    review = await gemini.structured_video(
        Path(ctx.state["preview_path"]).read_bytes(),
        PROMPT.format(
            sheet=_shot_sheet(cuts),
            missing=missing,
            history=_history(ctx.state.get("review_log", [])),
        ),
        SCHEMA,
        system=SYSTEM,
    )

    valid = {c["index"] for c in cuts}
    notes = [n for n in review["notes"] if n["cut_index"] in valid]
    wants_retake = review["decision"] == "retake" and notes

    if not wants_retake:
        verdict, accepted = "OK", True
    elif take < MAX_TAKES:
        verdict, accepted = "RETAKE", False
    else:
        # Out of takes. The reel moves on, but it is not signed off — the
        # screening room is told the director objected.
        verdict, accepted = "OK", False

    ctx.route = verdict
    if verdict == "RETAKE":
        ctx.state["take"] = take + 1
        ctx.state["retake_notes"] = notes
    else:
        ctx.state["retake_notes"] = []

    result = {
        "verdict": verdict,
        "take": take,
        "score": review["score"],
        "accepted": accepted,
        "protest": "" if accepted else review["comment"],
        "comment": review["comment"],
        "retakes": [n["cut_index"] for n in notes] if verdict == "RETAKE" else [],
        "issued": notes if verdict == "RETAKE" else [],
    }
    ctx.state["review"] = result
    ctx.state["review_log"] = [*ctx.state.get("review_log", []), result]
    return result
