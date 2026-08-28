"""Fact-check — checks the narration against the source material.

The films make factual claims about real shrines and waterfalls. The director
watches the picture and has nothing to say about whether the words are true, so
this reads every line back against the catalogue entry it came from.

A line that cannot be supported is replaced with one that can, rather than the
cut being dropped: the location is still worth showing.
"""

from __future__ import annotations

from google.adk import Context
from google.adk.workflow import node

from ..services import catalog, gemini

SYSTEM = """You are a fact-checker.
You judge whether a narration line contradicts the source material it is checked against.

The source material is in Japanese; the narration is in English. Read across the
language gap and match them on meaning, not surface wording.

Only stop a line for claims that would cause real harm if they were wrong:
  - Numbers (height, drop, tree age, area, headcount, era/year)
  - Proper nouns (people, shrine/temple names, place names)
  - Official designations or titles (World Heritage, National Treasure, nationally
    designated scenic spot, etc.)
  - The content of a legend or origin story

Do not stop a line for:
  - Evaluative or emotive language ("beautiful", "mystical", "hushed")
  - Scene-setting description that does not contradict the source
  - A paraphrase of a fact already in the source

If the line does not contradict the source and makes none of the four kinds of claim
above, supported=true.
When supported=false, corrected must always be written and must stay within what the
source supports. Keep numerals and the length and tone of the original line."""

SCHEMA = {
    "type": "object",
    "properties": {
        "supported": {"type": "boolean"},
        "issue": {"type": "string"},
        "corrected": {"type": "string"},
    },
    "required": ["supported", "issue", "corrected"],
}

PROMPT = """Source material ({name} / {area}), in Japanese:
Overview: {overview}
Highlights: {highlights}
Legend: {legend}

English narration line:
"{narration}"

Is this narration line supported by the source material above?"""


async def _verify(cut: dict) -> dict:
    spot = catalog.get(cut["spot_slug"])
    verdict = await gemini.structured(
        PROMPT.format(
            name=spot["name"],
            area=spot.get("area", ""),
            overview=spot.get("overview", ""),
            highlights=spot.get("highlights", ""),
            legend=spot.get("legend", ""),
            narration=cut["narration"],
        ),
        SCHEMA,
        system=SYSTEM,
    )
    return {
        "spot": spot["name"],
        "supported": bool(verdict["supported"]),
        "issue": verdict["issue"],
        "original": cut["narration"],
        "corrected": verdict["corrected"],
    }


@node
async def factcheck(ctx: Context) -> dict:
    import asyncio

    plan = ctx.state["plan"]
    results = await asyncio.gather(
        *(_verify(c) for c in plan["cuts"]), return_exceptions=True
    )

    corrections, unchecked = [], []
    for cut, r in zip(plan["cuts"], results):
        if isinstance(r, Exception):
            # An unverifiable line is left alone and said so, rather than
            # being passed off as checked.
            unchecked.append({"spot": cut["spot_slug"], "reason": str(r)})
            continue
        if not r["supported"] and r["corrected"]:
            cut["narration"] = r["corrected"]
            corrections.append(r)

    ctx.state["plan"] = plan
    ctx.state["fact_corrections"] = corrections
    ctx.state["fact_unchecked"] = unchecked
    return {
        "checked": len(plan["cuts"]) - len(unchecked),
        "corrected": len(corrections),
        "unchecked": unchecked,
        "changes": [
            {"spot": c["spot"], "issue": c["issue"]} for c in corrections
        ],
    }
