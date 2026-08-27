"""配信 — the only step that reaches outside the building.

Nothing arrives here without a person having watched the reel and said yes.
The credits the rights node worked out travel with it, since that is where the
attribution actually has to appear.
"""

from __future__ import annotations

from google.adk import Context
from google.adk.workflow import node

from ..services import youtube


def _description(ctx: Context) -> str:
    plan = ctx.state.get("plan", {})
    lines = [plan.get("theme", ""), ""]

    credits = [c for c in ctx.state.get("clearances", []) if c.get("credit")]
    if credits:
        lines.append("画像クレジット")
        lines += [f"  {c['spot']}: {c['credit']}" for c in credits]
        lines.append("")

    licence = ctx.state.get("work_licence")
    if licence:
        lines.append(f"本作のライセンス: {licence}")

    review = ctx.state.get("review", {})
    lines += [
        "",
        f"AIクルーが制作しました（take {review.get('take')}、監督評価 {review.get('score')}点）。",
    ]
    return "\n".join(lines).strip()


@node
async def delivery(ctx: Context) -> dict:
    d = ctx.state["delivery"]
    review = ctx.state.get("review", {})
    result = {
        **d,
        "screening_note": ctx.state.get("screening", {}).get("note", ""),
        "approved_on_take": review.get("take"),
        "score": review.get("score"),
        "director_comment": review.get("comment"),
    }

    if not youtube.configured():
        # Publishing is opt-in: without a channel the reel simply stays put.
        result |= {"published": False, "reason": "YouTube の認証情報が未設定です"}
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
        result |= {"published": True, **posted}
    except Exception as exc:
        # A failed upload must not read as a successful release.
        result |= {"published": False, "reason": f"{type(exc).__name__}: {exc}"}

    ctx.state["published"] = result
    return result


@node
async def abandoned(ctx: Context) -> dict:
    """The reel was screened and turned down. Nothing leaves the building."""
    return {
        "published": False,
        "reason": ctx.state.get("screening", {}).get("note") or "試写で公開が見送られました",
        "reel": ctx.state.get("delivery", {}).get("url"),
    }
