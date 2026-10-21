"""
Keyword classifier — PRD FR-04 / FR-09 / FR-11. Tier 2 of classification.

Deterministic whole-word matching of OCR text against products.json. This is
the fallback behind services/vision_classifier.py: it runs when vision is
disabled (no API credential), when the vision call fails, or when vision
returns "Unknown" but OCR still read a usable label. It's also what keeps
the demo working offline.

Confidence here is a match-count heuristic, not a calibrated probability —
the vision tier is the one that reports an honest confidence.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from backend.services.ocr_service import OcrResult

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "products.json"

# Below this, the result is treated as "Unknown" rather than forcing a
# classification — PRD FR-11.
CONFIDENCE_THRESHOLD = 0.5

UNKNOWN_ITEM = "Unknown Item"
UNKNOWN_CATEGORY = "Unknown"


@dataclass
class ClassificationResult:
    item: str
    category: str
    confidence: float
    is_unknown: bool
    matched_keywords: List[str]
    # Internal taxonomy key (PRD v1.1 §2.3 list) — drives the hazard/
    # disposal/recovery rule lookups in the next stages. Not shown to the
    # user directly; "item"/"category" above are the display strings.
    internal_category: Optional[str]


def _load_products() -> dict:
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_PRODUCTS = _load_products()
_CATEGORY_PRIORITY = _PRODUCTS["_priority_order"]

# Whole-word matching. A bare substring test made "pcb" hit inside "upcbx",
# "ssd" inside "passd", "processor" inside "microprocessor" and so on —
# false positives that then got a "confident" score. OCR output is also
# hyphen/space-noisy, so any whitespace or hyphen run in a keyword matches
# any whitespace/hyphen run in the text ("power bank" == "power-bank").
_KEYWORD_PATTERNS = {
    kw: re.compile(r"(?<![a-z0-9])" + r"[\s\-]+".join(re.escape(p) for p in re.split(r"[\s\-]+", kw)) + r"(?![a-z0-9])")
    for cat in _PRODUCTS["categories"].values()
    for kw in cat["keywords"]
}


def classify(ocr_result: OcrResult) -> ClassificationResult:
    if not ocr_result.has_useful_text:
        return _unknown(confidence=0.0, matched_keywords=[])

    searchable = _build_searchable_text(ocr_result)

    best_category = None
    best_score = 0
    best_matches: List[str] = []

    for cat_key in _CATEGORY_PRIORITY:
        cat = _PRODUCTS["categories"][cat_key]
        matches = [kw for kw in cat["keywords"] if _KEYWORD_PATTERNS[kw].search(searchable)]
        if len(matches) > best_score:
            best_score = len(matches)
            best_category = cat_key
            best_matches = matches

    if best_category is None:
        return _unknown(confidence=0.0, matched_keywords=[])

    confidence = _score_to_confidence(best_score, ocr_result)

    if confidence < CONFIDENCE_THRESHOLD:
        return _unknown(confidence=confidence, matched_keywords=best_matches)

    cat_def = _PRODUCTS["categories"][best_category]
    return ClassificationResult(
        item=cat_def["item_name"],
        category=cat_def["category_label"],
        confidence=confidence,
        is_unknown=False,
        matched_keywords=best_matches,
        internal_category=best_category,
    )


def _unknown(confidence: float, matched_keywords: List[str]) -> ClassificationResult:
    return ClassificationResult(
        item=UNKNOWN_ITEM,
        category=UNKNOWN_CATEGORY,
        confidence=confidence,
        is_unknown=True,
        matched_keywords=matched_keywords,
        internal_category=None,
    )


def _build_searchable_text(ocr_result: OcrResult) -> str:
    parts = [ocr_result.raw_text.lower()]
    if ocr_result.fields.model_number:
        parts.append(ocr_result.fields.model_number.lower())
    return " ".join(parts)


def _score_to_confidence(match_count: int, ocr_result: OcrResult) -> float:
    # Deterministic, capped curve — more distinctive-keyword hits means
    # higher confidence, with diminishing returns. A detected battery_type
    # field (from OCR field extraction, e.g. "lithium-ion") is corroborating
    # evidence regardless of which category won, so it gets a small boost.
    base = min(0.4 + 0.15 * match_count, 0.95)
    if ocr_result.fields.battery_type:
        base = min(base + 0.05, 0.97)
    return round(base, 2)
