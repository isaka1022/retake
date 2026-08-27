"""試写 — the last gate before the film leaves the building.

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
            f"『{delivery.get('title', '')}』 {delivery.get('seconds', 0)}秒 "
            f"/ {delivery.get('cuts', 0)}カット / take {review.get('take')}",
            f"素材ライセンス: {ctx.state.get('work_licence', '不明')}",
            f"監督の採点: {review.get('score')}点",
        ]
        missing = delivery.get("missing_cuts") or []
        if missing:
            # The director scored what was assembled, not what was planned.
            lines.append(
                f"⚠ 計画 {delivery.get('planned_cuts')} カットのうち "
                f"{len(missing)} カットが撮影できず、欠けたまま編集されています"
                f"（カット {', '.join(str(m) for m in missing)}）"
            )
        if not review.get("accepted", False):
            lines.append(f"⚠ 監督は承服していません: {review.get('protest', '')}")
        lines.append("公開してよいか判断してください。")

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
