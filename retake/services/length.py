"""How long a film runs, and how many cuts it is cut into.

The defaults describe the thirty-second films the crew was built for. A longer
brief needs more cuts than that, so the policy is read from the environment
rather than baked into the planner's prompt.
"""

from __future__ import annotations

import os


def _number(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


#: Seconds a single cut runs once it has been narrated.
CUT_SECONDS = _number("RETAKE_CUT_SECONDS", 8.0)

#: Bounds on how many cuts one film may be built from.
MIN_CUTS = int(_number("RETAKE_MIN_CUTS", 2))
MAX_CUTS = int(_number("RETAKE_MAX_CUTS", 4))

#: Bounds on a single shot's on-screen length, in seconds.
MIN_SHOT_SECONDS = _number("RETAKE_MIN_SHOT_SECONDS", 3.0)
MAX_SHOT_SECONDS = _number("RETAKE_MAX_SHOT_SECONDS", 12.0)
