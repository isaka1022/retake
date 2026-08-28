"""Rights — clears every still before it reaches the edit.

A shot that cannot be cleared is pulled from the plan rather than quietly
published, which is the whole point of having this member on the crew.
"""

from __future__ import annotations

from google.adk import Context
from google.adk.workflow import node

from ..services import catalog, rights


@node
async def rights_check(ctx: Context) -> dict:
    shots = ctx.state["shots"]
    cleared, blocked = [], []

    for shot in shots:
        spot = catalog.get(shot["spot_slug"])
        c = rights.clear(spot["slug"], spot.get("image"))
        entry = {
            "index": shot["index"],
            "spot": spot["name"],
            "credit": c.credit,
            "share_alike": c.share_alike,
            "reason": c.reason,
        }
        (cleared if c.usable else blocked).append(entry)

    usable = [rights.clear(catalog.get(s["spot_slug"])["slug"],
                           catalog.get(s["spot_slug"]).get("image")) for s in shots]
    licence = rights.work_licence(usable)

    # Kept as a list: state is serialised as JSON between runs, and integer
    # dict keys come back as strings.
    ctx.state["clearances"] = cleared
    ctx.state["blocked_shots"] = [b["index"] for b in blocked]
    ctx.state["work_licence"] = licence

    return {"cleared": len(cleared), "blocked": blocked, "work_licence": licence}
