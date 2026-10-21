"""
Recovery potential engine — PRD FR-08, v1.1 §2.9.

Category-based only, per data/recovery_rules.json — deliberately never
attempts to estimate exact metal quantity or monetary value from a photo
(explicit PRD non-goal, §1 / §2.9).
"""

import json
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "recovery_rules.json"


def _load_rules() -> dict:
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_RULES = _load_rules()
_CATEGORY_MAP = _RULES["category_recovery_map"]

UNKNOWN_RECOVERY_POTENTIAL = "unknown"


def get_recovery_potential(internal_category: Optional[str]) -> str:
    if internal_category is None:
        return UNKNOWN_RECOVERY_POTENTIAL

    return _CATEGORY_MAP.get(internal_category, UNKNOWN_RECOVERY_POTENTIAL)
