"""Screening — the last gate before the film leaves the building.

Publishing is not reversible, so a person watches the reel and decides. When
the director never signed off, the objection is put in front of them rather
than being smoothed over.
"""

from __future__ import annotations

from typing import Any

from google.adk import Context
from google.adk.events import RequestInput
from google.adk.workflow import node

SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["publish", "retake", "abandon"]},
        "note": {"type": "string"},
    },
    "required": ["decision"],
}


def _answer(ctx: Context, interrupt_id: str) -> dict[str, Any] | None:
    inputs = ctx.resume_inputs or {}
    if interrupt_id in inputs:
        return inputs[interrupt_id]
    # The id is regenerated per attempt; a lone pending answer is still ours.
    return next(iter(inputs.values())) if len(inputs) == 1 else None


@node(rerun_on_resume=True)
async def screening(ctx: Context) -> Any:
    review = ctx.state.get("review", {})
    delivery = ctx.state.get("delivery", {})
    interrupt_id = f"screening-{ctx.invocation_id}-{review.get('take', 1)}"

    answer = _answer(ctx, interrupt_id)
    if answer is None:
        lines = [
            f"\"{delivery.get('title', '')}\" {delivery.get('seconds', 0)}s "
            f"/ {delivery.get('cuts', 0)} cuts / take {review.get('take')}",
            f"Footage licence: {ctx.state.get('work_licence', 'unknown')}",
            f"Director's score: {review.get('score')}",
        ]
        missing = delivery.get("missing_cuts") or []
        if missing:
            # The director scored what was assembled, not what was planned.
            lines.append(
                f"⚠ {len(missing)} of {delivery.get('planned_cuts')} planned cuts "
                f"could not be shot and the edit went out short "
                f"(cuts {', '.join(str(m) for m in missing)})"
            )
        if not review.get("accepted", False):
            lines.append(f"⚠ The director did not sign off: {review.get('protest', '')}")
        lines.append("Decide whether this is ready to publish.")

        return RequestInput(
            interruptId=interrupt_id,
            message="\n".join(lines),
            payload={
                "reel": delivery.get("url"),
                "director_accepted": review.get("accepted", False),
                "work_licence": ctx.state.get("work_licence"),
            },
            responseSchema=SCHEMA,
        )

    decision = (answer or {}).get("decision", "abandon")
    ctx.state["screening"] = {"decision": decision, "note": (answer or {}).get("note", "")}
    ctx.route = {"publish": "PUBLISH", "retake": "RETAKE"}.get(decision, "ABANDON")
    return ctx.state["screening"]
