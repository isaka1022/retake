"""絵コンテ — assigns concrete camera moves to each cut."""

from __future__ import annotations

from google.adk import Context
from google.adk.workflow import node

from ..services import catalog, gemini

MOTIONS = ["push_in", "pan_left", "pan_right"]

SYSTEM = """あなたは映像作品の絵コンテ担当です。
各カットにカメラワークを割り当てます。同じ動きが3回続かないようにしてください。

カットの作り方は2通りあります。
- still: 素材写真にカメラワークを与える。確実で速い
- veo: 素材写真から映像を生成する。水や木々が実際に動くが、生成に約50秒かかり費用もかかる

veo は最も動きが効く1カットだけに使ってください。動きのない被写体には使いません。"""

SCHEMA = {
    "type": "object",
    "properties": {
        "shots": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "spot_slug": {"type": "string"},
                    "seconds": {"type": "number"},
                    "motion": {"type": "string", "enum": MOTIONS},
                    "zoom_to": {"type": "number"},
                    "caption": {"type": "string"},
                    "source": {"type": "string", "enum": ["still", "veo"]},
                    "motion_prompt": {"type": "string"},
                },
                "required": [
                    "spot_slug", "seconds", "motion", "zoom_to", "caption",
                    "source", "motion_prompt",
                ],
            },
        }
    },
    "required": ["shots"],
}


@node
async def storyboard(ctx: Context) -> dict:
    plan = ctx.state["plan"]
    lines = "\n".join(
        f"{i}. {catalog.get(c['spot_slug'])['name']} / ナレーション「{c['narration']}」"
        f" / 意図: {c['visual_intent']}"
        for i, c in enumerate(plan["cuts"])
    )
    board = await gemini.structured(
        f"作品タイトル「{plan['title']}」\n\nカット:\n{lines}\n\n"
        "各カットに seconds（4〜10）、motion、zoom_to（1.05〜1.30）、"
        "画面に出すテロップ caption（15文字以内）、source、"
        "そして source が veo のときに何がどう動くかを述べる motion_prompt を"
        "割り当ててください。still のカットにも motion_prompt は空文字で構いません。",
        SCHEMA,
        system=SYSTEM,
    )
    shots = []
    for i, s in enumerate(board["shots"][: len(plan["cuts"])]):
        spot = catalog.get(s["spot_slug"]) or catalog.get(plan["cuts"][i]["spot_slug"])
        shots.append(
            {
                "index": i,
                "spot_slug": spot["slug"],
                "seconds": min(max(float(s["seconds"]), 3.0), 12.0),
                "motion": s["motion"] if s["motion"] in MOTIONS else "push_in",
                "zoom_to": min(max(float(s["zoom_to"]), 1.02), 1.4),
                "caption": s["caption"],
                "narration": plan["cuts"][i]["narration"],
                "source": s["source"],
                "motion_prompt": s.get("motion_prompt", ""),
            }
        )

    # Generation is billed per second and the director may call for several
    # takes, so only the strongest candidate is generated.
    generated = [s for s in shots if s["source"] == "veo"]
    for extra in generated[1:]:
        extra["source"] = "still"
    ctx.state["shots"] = shots
    return {"shots": shots}
