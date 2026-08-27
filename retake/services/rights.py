"""Licence rules for the stills the crew shoots from.

The catalogue mixes CC0, CC BY and CC BY-SA. They do not impose the same
obligations, and share-alike propagates to the finished film, so the decision
cannot be a fixed credit string pasted at the end.
"""

from __future__ import annotations

from dataclasses import dataclass

# Attribution is required unless the licence waives it; share-alike binds the
# work that embeds the still, not just the still.
_ATTRIBUTION_FREE = {"CC0", "PUBLIC DOMAIN", "PD"}
_SHARE_ALIKE_MARKER = "-SA"


@dataclass(frozen=True)
class Clearance:
    slug: str
    usable: bool
    credit: str | None
    share_alike: bool
    reason: str


def _normalise(licence: str | None) -> str:
    return (licence or "").strip().upper()


def clear(slug: str, image: dict | None) -> Clearance:
    """Decide whether one still may be used, and on what terms."""
    if not image or not image.get("url"):
        return Clearance(slug, False, None, False, "素材そのものがありません")

    licence = _normalise(image.get("license"))
    if not licence:
        return Clearance(slug, False, None, False, "ライセンスが不明です")

    artist = (image.get("artist") or "").strip()
    waived = any(licence.startswith(f) for f in _ATTRIBUTION_FREE)

    if not waived and not artist:
        return Clearance(
            slug, False, None, False, f"{licence} は帰属表示が必須ですが著作者が不明です"
        )

    share_alike = _SHARE_ALIKE_MARKER in licence
    if waived:
        credit = None
        reason = f"{licence} のため表示義務なし"
    else:
        credit = f"{artist} / {image['license']}"
        reason = f"{licence} のため帰属表示を焼き込みます"

    return Clearance(slug, True, credit, share_alike, reason)


def work_licence(clearances: list[Clearance]) -> str:
    """Share-alike on any single still binds the finished film."""
    if any(c.share_alike for c in clearances if c.usable):
        return "CC BY-SA 4.0"
    if any(c.credit for c in clearances if c.usable):
        return "CC BY 4.0"
    return "全素材がパブリックドメイン相当"
