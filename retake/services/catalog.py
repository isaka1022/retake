"""The location library the crew shoots from."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG = Path(__file__).resolve().parent.parent / "assets" / "catalog.json"


@lru_cache(maxsize=1)
def spots() -> list[dict[str, Any]]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def by_slug() -> dict[str, dict[str, Any]]:
    return {s["slug"]: s for s in spots()}


def get(slug: str) -> dict[str, Any] | None:
    return by_slug().get(slug)


def brief_for_llm() -> str:
    """A compact index the planner can choose locations from."""
    return "\n".join(
        f"- {s['slug']} | {s['name']}（{s['area']}）: {s['overview']}" for s in spots()
    )
