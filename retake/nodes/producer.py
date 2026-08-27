"""企画 — turns a one-line brief into a shot plan."""

from __future__ import annotations

from google.adk import Context
from google.adk.workflow import node

from ..services import catalog, gemini

SYSTEM = """あなたは短編ドキュメンタリーの構成作家です。
与えられたロケ地リストから、依頼に合う場所だけを選び、30秒前後の映像の構成を書きます。
ナレーションは一文が長すぎないこと。事実に基づき、誇張しないこと。"""

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

DEFAULT_BRIEF = "日本のパワースポットを30秒で紹介する"


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
        f"依頼: {brief}\n\n"
        f"選べるロケ地:\n{catalog.brief_for_llm()}\n\n"
        "3〜4か所を選び、各カットのナレーションと画づくりの意図を書いてください。",
        SCHEMA,
        system=SYSTEM,
    )
    # A hallucinated slug would break the shoot; drop it here rather than later.
    plan["cuts"] = [c for c in plan["cuts"] if catalog.get(c["spot_slug"])]
    ctx.state["brief"] = brief
    ctx.state["plan"] = plan
    return plan
