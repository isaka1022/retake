"""監督 — watches the cut and decides whether it ships.

The review is a real one: the reel is handed to Gemini as video, not described
to it. Every note carries the full replacement setup, so a retake is always
something the crew can actually execute — a note the camera cannot act on would
loop forever without improving the reel.
"""

from __future__ import annotations

from pathlib import Path

from google.adk import Context
from google.adk.workflow import node

from ..services import gemini

QUALITY_BAR = 70
MAX_TAKES = 3

SYSTEM = """あなたは短編映像の監督です。妥協せず、具体的に指摘します。
使えるのは素材写真1枚からのカメラワークと露出調整だけです。
撮り直しの指示は必ずこの2つの範囲で出してください。実現できない要求は書きません。

あなたは自分が前回出した指示を憶えています。撮り直しの回では、粗探しを最初からやり直すのではなく
「前回の指摘は解消したか」「前回より良くなったか」で判断してください。
素材の限界でこれ以上良くならないと判断したなら、完璧でなくても ship してください。
同じ指摘を3回繰り返すのは、指示が悪いか、素材の限界です。"""

NOTE = {
    "type": "object",
    "properties": {
        "cut_index": {"type": "integer"},
        "problem": {"type": "string"},
        "motion": {"type": "string", "enum": ["push_in", "pan_left", "pan_right"]},
        "zoom_to": {"type": "number"},
        "seconds": {"type": "number"},
        "exposure": {"type": "number"},
        "contrast": {"type": "number"},
    },
    "required": [
        "cut_index", "problem", "motion", "zoom_to", "seconds", "exposure", "contrast",
    ],
}

SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer"},
        "decision": {"type": "string", "enum": ["ship", "retake"]},
        "comment": {"type": "string"},
        "notes": {"type": "array", "items": NOTE},
    },
    "required": ["score", "decision", "comment", "notes"],
}

PROMPT = """この映像を審査してください。カットの割りと今回の設定は以下のとおりです。

{sheet}
{history}
100点満点で採点し、出すか撮り直すかを decision で答えてください。
撮り直すなら、直すべきカットに指示を出します。
指示には必ず次をすべて含めてください。
- motion: カメラワーク
- zoom_to: 寄りの強さ 1.02〜1.40
- seconds: 尺 3〜12
- exposure: 明るさ補正 -0.30〜0.30（白飛びは負の値で抑える）
- contrast: コントラスト 0.80〜1.30

問題がなければ notes は空にしてください。"""


def _history(log: list[dict]) -> str:
    """What the director already asked for. Without it each review starts from
    scratch and the loop never converges."""
    if not log:
        return ""
    lines = ["\nこれまでのあなたの判断:"]
    for r in log:
        asked = "、".join(
            f"カット{n['cut_index']}（{n['problem']}）" for n in r.get("issued", [])
        )
        lines.append(f"  take {r['take']}: {r['score']}点 — {r['comment']}")
        if asked:
            lines.append(f"    出した指示: {asked}")
    lines.append("これらが今回どう反映されたかを見て判断してください。")
    return "\n".join(lines) + "\n"


def _shot_sheet(cuts: list[dict]) -> str:
    lines, at = [], 0.0
    for c in sorted(cuts, key=lambda x: x["index"]):
        if c.get("source") == "veo":
            # A generated shot cannot be recomposed without paying to make it
            # again, so only the grade is on the table.
            lines.append(
                f"カット{c['index']}: {at:.1f}〜{at + c['seconds']:.1f}秒 / 生成ショット"
                f"（カメラワークは変更不可・露出のみ調整可） / "
                f"exposure {c.get('exposure', 0.0):+.2f} / "
                f"contrast {c.get('contrast', 1.0):.2f}"
            )
        else:
            lines.append(
                f"カット{c['index']}: {at:.1f}〜{at + c['seconds']:.1f}秒 / {c['motion']} / "
                f"zoom {c['zoom_to']:.2f} / exposure {c.get('exposure', 0.0):+.2f} / "
                f"contrast {c.get('contrast', 1.0):.2f}"
            )
        at += c["seconds"]
    return "\n".join(lines)


@node
async def director(ctx: Context) -> dict:
    take = ctx.state.get("take", 1)
    cuts = ctx.state["cuts"]

    review = await gemini.structured_video(
        Path(ctx.state["preview_path"]).read_bytes(),
        PROMPT.format(
            sheet=_shot_sheet(cuts),
            history=_history(ctx.state.get("review_log", [])),
        ),
        SCHEMA,
        system=SYSTEM,
    )

    valid = {c["index"] for c in cuts}
    notes = [n for n in review["notes"] if n["cut_index"] in valid]
    wants_retake = review["decision"] == "retake" and notes

    if not wants_retake:
        verdict, accepted = "OK", True
    elif take < MAX_TAKES:
        verdict, accepted = "RETAKE", False
    else:
        # Out of takes. The reel moves on, but it is not signed off — the
        # screening room is told the director objected.
        verdict, accepted = "OK", False

    ctx.route = verdict
    if verdict == "RETAKE":
        ctx.state["take"] = take + 1
        ctx.state["retake_notes"] = notes
    else:
        ctx.state["retake_notes"] = []

    result = {
        "verdict": verdict,
        "take": take,
        "score": review["score"],
        "accepted": accepted,
        "protest": "" if accepted else review["comment"],
        "comment": review["comment"],
        "retakes": [n["cut_index"] for n in notes] if verdict == "RETAKE" else [],
        "issued": notes if verdict == "RETAKE" else [],
    }
    ctx.state["review"] = result
    ctx.state["review_log"] = [*ctx.state.get("review_log", []), result]
    return result
