"""
Disposal rule engine — PRD FR-07, v1.1 §2.10 / §2.8 / §4.

"Rules govern safety": this is the deterministic Python layer the PRD
insists on instead of letting a generative layer freely decide hazardous-
handling guidance. Category -> disposal_category comes from
data/disposal_rules.json; the damage override below is enforced in code
(not data) so it can never be silently dropped by editing the JSON file —
PRD v1.1 §2.8's principle "Safety > Disposal > Recovery Value, never
reversed" is non-negotiable and takes priority over whatever the category
would normally map to.
"""

import json
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "disposal_rules.json"


def _load_rules() -> dict:
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_RULES = _load_rules()
_CATEGORY_MAP = _RULES["category_disposal_map"]
_DAMAGE_OVERRIDE = _RULES["damage_override_category"]

UNKNOWN_DISPOSAL_CATEGORY = "unknown"


def get_disposal_category(internal_category: Optional[str], damage_detected: bool) -> str:
    # PRD v1.1 §2.8: a damaged/leaking/swollen item is always escalated,
    # regardless of what its category would normally resolve to.
    if damage_detected:
        return _DAMAGE_OVERRIDE

    if internal_category is None:
        return UNKNOWN_DISPOSAL_CATEGORY

    return _CATEGORY_MAP.get(internal_category, UNKNOWN_DISPOSAL_CATEGORY)
