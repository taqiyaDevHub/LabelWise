"""
Material analysis — PRD FR-05 (material analysis), FR-06 (hazard detection),
v1.1 §2.5 / §2.6.

JSON-driven, same philosophy as classifier.py: deterministic lookups against
data/materials.json rather than an LLM guessing composition from pixels.
PRD §9 / §2.5 is explicit that a photo can't establish exact chemistry, so
this module never invents a battery chemistry beyond what OCR actually
detected — categories with a battery default to an "unknown"-hazard generic
cell unless `ocr_result.fields.battery_type` (from ocr_service's regex/
keyword extraction) names a specific one, in which case the specific,
correctly-hazarded material is used instead.

hazard values are validated against schemas.HazardLevel by Pydantic when the
route builds the final AnalysisResult, so a typo in materials.json surfaces
immediately as a 500 in dev rather than a silently wrong hazard reaching a
user.
"""

import json
from pathlib import Path
from typing import List, Optional

from backend.models.schemas import Material
from backend.services.ocr_service import OcrResult

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "materials.json"


def _load_materials() -> dict:
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_MATERIALS = _load_materials()


def analyze_materials(internal_category: Optional[str], ocr_result: OcrResult) -> List[Material]:
    """Return the material/hazard breakdown for a classified item.

    internal_category: classifier.ClassificationResult.internal_category.
    None (unknown item) should never reach here in practice — the route
    returns the uncertainty response before calling this — but returning an
    empty list rather than raising keeps this function safe to call
    defensively.
    """
    if internal_category is None:
        return []

    cat_def = _MATERIALS["categories"].get(internal_category)
    if cat_def is None:
        return []

    materials: List[Material] = []

    if "battery_material_default" in cat_def:
        battery_type = ocr_result.fields.battery_type
        overrides = cat_def.get("battery_type_overrides", {})
        chosen = overrides.get(battery_type) if battery_type else None
        if chosen is None:
            chosen = cat_def["battery_material_default"]
        materials.append(Material(**chosen))

    for m in cat_def.get("other_materials", []):
        materials.append(Material(**m))

    return materials
