"""Producer — turns a one-line brief into a shot plan."""

from __future__ import annotations

from google.adk import Context
from google.adk.workflow import node

from ..services import catalog, gemini

SYSTEM = """You are the writer for a short documentary.
The location list you are given is in Japanese: read it carefully, then choose only the
locations that fit the brief and write the roughly 30-second film plan in English.
Keep narration sentences short. Stay factual and avoid exaggeration."""

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "theme": {"type": "string"},
        "cuts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "spot_slug": {"type": "string"},
                    "narration": {"type": "string"},
                    "visual_intent": {"type": "string"},
                },
                "required": ["spot_slug", "narration", "visual_intent"],
            },
        },
    },
    "required": ["title", "theme", "cuts"],
}

DEFAULT_BRIEF = "Introduce Japan's power spots in 30 seconds"


def _brief(ctx: Context) -> str:
    content = ctx.user_content
    if content and content.parts:
        text = " ".join(p.text for p in content.parts if p.text).strip()
        if text:
            return text
    return ctx.state.get("brief") or DEFAULT_BRIEF


@node
async def producer(ctx: Context) -> dict:
    brief = _brief(ctx)
    plan = await gemini.structured(
        f"Brief: {brief}\n\n"
        f"Available locations (source material is in Japanese, write your answer in English):\n"
        f"{catalog.brief_for_llm()}\n\n"
        "Choose 3 to 4 locations. For each cut, write the narration and describe the "
        "visual intent, in English.",
        SCHEMA,
        system=SYSTEM,
    )
    # A hallucinated slug would break the shoot; drop it here rather than later.
    plan["cuts"] = [c for c in plan["cuts"] if catalog.get(c["spot_slug"])]
    ctx.state["brief"] = brief
    ctx.state["plan"] = plan
    return plan
