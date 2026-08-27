"""A spending ceiling for one film.

Generation is the only part of the crew that bills per use, and the director
decides how many takes to call for. Without a ceiling a single brief can spend
without bound, so the shoot asks before it generates and falls back to a still
when the money is gone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Veo 3.1 Fast, 720p. The other models cost orders of magnitude less and are
# counted rather than priced.
VEO_USD_PER_SECOND = 0.10

DEFAULT_CEILING_USD = 2.50


@dataclass
class Ledger:
    ceiling_usd: float = DEFAULT_CEILING_USD
    spent_usd: float = 0.0
    entries: list[dict] = field(default_factory=list)

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.ceiling_usd - self.spent_usd)

    def can_afford(self, usd: float) -> bool:
        return usd <= self.remaining_usd

    def charge(self, what: str, usd: float, note: str = "") -> None:
        self.spent_usd += usd
        self.entries.append({"what": what, "usd": round(usd, 4), "note": note})

    def to_state(self) -> dict:
        return {
            "ceiling_usd": self.ceiling_usd,
            "spent_usd": round(self.spent_usd, 4),
            "entries": self.entries,
        }

    @classmethod
    def from_state(cls, data: dict | None) -> "Ledger":
        if not data:
            return cls()
        return cls(
            ceiling_usd=data.get("ceiling_usd", DEFAULT_CEILING_USD),
            spent_usd=data.get("spent_usd", 0.0),
            entries=list(data.get("entries", [])),
        )


def veo_cost(seconds: float) -> float:
    return seconds * VEO_USD_PER_SECOND
