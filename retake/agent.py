"""Retake — an AI film crew as an ADK graph workflow.

Day 0 skeleton: validates the graph engine, conditional routing and the
retake cycle with pure-function nodes (no LLM calls yet).
"""

from __future__ import annotations

from google.adk import Context, Workflow
from google.adk.workflow import START, node

# The director accepts a cut once it reaches this score.
QUALITY_BAR = 70
MAX_RETAKES = 2


@node
async def plan(ctx: Context) -> dict:
    """企画・構成: turn a brief into a shot plan."""
    brief = ctx.state.get("brief", "御岩神社を30秒で紹介する")
    return {"brief": brief, "shots": 3}


@node
async def shoot(ctx: Context) -> dict:
    """撮影: produce cuts. Quality improves on each retake."""
    take = ctx.state.get("take", 0) + 1
    # Stand-in for real generation: the first take is deliberately weak.
    cut = {"take": take, "score": 40 + take * 25}
    ctx.state["take"] = take
    ctx.state["cut"] = cut
    return cut


@node
async def review(ctx: Context, cut: dict) -> dict:
    """監督: accept the cut or order a retake."""
    score, take = cut["score"], cut["take"]
    verdict = "RETAKE" if score < QUALITY_BAR and take <= MAX_RETAKES else "OK"
    ctx.route = verdict
    result = {"verdict": verdict, "score": score, "take": take}
    ctx.state["verdict"] = result
    return result


@node
async def deliver(ctx: Context, verdict: dict) -> str:
    """配信: the terminal node."""
    return f"delivered take {verdict['take']} (score {verdict['score']})"


root_agent = Workflow(
    name="retake",
    description="An AI film crew that shoots, reviews and retakes until the cut is good enough.",
    edges=[
        (START, plan),
        (plan, shoot),
        (shoot, review),
        (review, {"RETAKE": shoot, "OK": deliver}),
    ],
)
