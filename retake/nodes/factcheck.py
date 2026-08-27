"""校正 — checks the narration against the source material.

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

SYSTEM = """あなたは事実確認の担当です。
ナレーション原稿が、与えられた資料と矛盾していないかを判定します。

止めるのは、間違っていれば実害の出る主張だけです。
  - 数値（高さ・落差・樹齢・面積・人数・年代）
  - 固有名詞（人名・寺社名・地名）
  - 公式な指定や肩書き（世界遺産・国宝・国指定名勝など）
  - 由緒・伝承の内容

止めないもの:
  - 「美しい」「神秘的」「静寂に満ちた」といった評価・情感の表現
  - 資料と矛盾しない範囲での情景描写
  - 資料に書かれた事実の言い換え

資料と矛盾せず、上の4種類の具体的な主張を含まないなら supported=true です。
supported=false のときは、資料の範囲内に収めた corrected を必ず書いてください。
数字は原稿と同じ半角で書き、長さと調子は保ってください。"""

SCHEMA = {
    "type": "object",
    "properties": {
        "supported": {"type": "boolean"},
        "issue": {"type": "string"},
        "corrected": {"type": "string"},
    },
    "required": ["supported", "issue", "corrected"],
}

PROMPT = """資料（{name} / {area}）:
概要: {overview}
見どころ: {highlights}
伝承: {legend}

ナレーション原稿:
「{narration}」

この原稿は上の資料だけで裏づけられますか。"""


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
