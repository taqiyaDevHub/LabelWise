"""
Guidance engine — the "What should I do now?" steps (PRD v1.1 §2.10).

JSON-driven like the other rules engines. Previously this lived in the
frontend as mock presentation data; moving it here makes the backend the
single source of truth for user-facing safety guidance and lets any client
(Streamlit, web, mobile) render identical steps.

Damage steps are enforced in code, not data: a damaged item ALWAYS gets the
damage steps, whatever the disposal category resolved to.
"""

import json
from pathlib import Path
from typing import List

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "guidance.json"


def _load() -> dict:
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_GUIDANCE = _load()
_DAMAGE_STEPS: List[str] = _GUIDANCE["damage_steps"]
_BY_CATEGORY: dict = _GUIDANCE["by_disposal_category"]


def get_guidance_steps(disposal_category: str, damage_detected: bool) -> List[str]:
    if damage_detected:
        return list(_DAMAGE_STEPS)
    return list(_BY_CATEGORY.get(disposal_category, _BY_CATEGORY["unknown"]))
