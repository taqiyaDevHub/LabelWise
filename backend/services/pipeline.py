"""
The analysis pipeline as a plain function — no HTTP.

validate -> preprocess -> OCR -> classify (vision, keyword fallback)
         -> materials -> disposal -> recovery -> guidance -> AnalysisResult

Two callers:
  - routes/analyze.py            wraps it in POST /analyze (JSON contract)
  - frontend LocalAnalysisService calls it in-process for single-app deploys
    (Streamlit Community Cloud) where there is no separate backend server.

Classification is a two-tier strategy:
  1. Vision (services/vision_classifier.py) — a vision model looks at the
     actual photo and returns item, confidence + reasoning, materials with
     per-material confidence, and visible damage. Used whenever an API
     credential is configured.
  2. Keyword (services/classifier.py) — deterministic OCR-text matching.
     Used when vision is disabled/unavailable, when the vision call fails,
     or when vision itself says "Unknown" (a readable label can still rescue
     a photo the model wasn't sure about).

Safety decisions stay in the rules engines regardless of which tier
classified the item: disposal_engine enforces the damage override in code,
recovery_engine is category-only, guidance_engine forces damage steps.
"""

import logging
from typing import List, Optional

from backend.models.schemas import AnalysisResult, Evidence, Material
from backend.services import vision_classifier
from backend.services.classifier import classify as keyword_classify
from backend.services.disposal_engine import get_disposal_category
from backend.services.guidance_engine import get_guidance_steps
from backend.services.image_validator import validate_image
from backend.services.material_analyzer import analyze_materials
from backend.services.ocr_service import OcrResult, run_ocr
from backend.services.preprocess import preprocess_image
from backend.services.recovery_engine import get_recovery_potential

logger = logging.getLogger("labelwise.pipeline")

# Exact PRD-defined string (PRD §5 / §2.2). Do not reword.
POOR_QUALITY_MESSAGE = "We can't confidently analyze this image. Please upload a clearer photo."


class AnalysisUncertain(Exception):
    """Raised when neither tier can classify the image with enough evidence
    (PRD FR-11: never invent a classification). Carries the exact
    user-facing message."""

    def __init__(self, message: str = POOR_QUALITY_MESSAGE):
        self.message = message
        super().__init__(message)


def analyze_image(contents: bytes, filename: Optional[str], content_type: Optional[str]) -> AnalysisResult:
    """Run the full pipeline on raw upload bytes.

    Raises:
        image_validator.ImageValidationError — bad type / too large / corrupt
        AnalysisUncertain                    — no confident classification
    """
    validate_image(filename=filename, declared_content_type=content_type, contents=contents)

    # Preprocessing/OCR never fail the request on their own — a bad frame or
    # a missing/broken Tesseract install degrades to "no text", not a crash.
    preprocessed = preprocess_image(contents)
    ocr_result = run_ocr(preprocessed.ocr_image)

    # --- Tier 1: vision ---
    vision = vision_classifier.classify(preprocessed.display_image, ocr_result)
    if vision is None:
        logger.info("vision: unavailable or failed (provider=%s) -> keyword fallback", vision_classifier.provider())
    elif vision.is_unknown:
        logger.info("vision: model answered Unknown (confidence=%.2f, reason=%r) -> keyword fallback",
                    vision.confidence, vision.reasoning[:120])
    else:
        logger.info("vision: %s (%.2f) via %s", vision.item, vision.confidence, vision_classifier.provider())

    if vision is not None and not vision.is_unknown:
        return _build_from_vision(vision, ocr_result)

    # --- Tier 2: keyword fallback ---
    keyword = keyword_classify(ocr_result)
    if keyword.is_unknown:
        # Also covers "OCR found no useful text" under the same user-facing
        # message, since both boil down to "not enough evidence".
        raise AnalysisUncertain()

    # Vision may have run and returned Unknown for the *category* while still
    # seeing damage or reading text — keep that evidence, it's real.
    damage_detected = bool(vision and vision.damage_detected)
    damage_description = vision.damage_description if vision else None
    internal_category = keyword.internal_category

    materials = analyze_materials(internal_category, ocr_result)
    disposal_category = get_disposal_category(internal_category, damage_detected)

    return AnalysisResult(
        item=keyword.item,
        category=keyword.category,
        confidence=keyword.confidence,
        materials=materials,
        damage_detected=damage_detected,
        recovery_potential=get_recovery_potential(internal_category),
        disposal_category=disposal_category,
        brand_model=None,
        damage_description=damage_description,
        reasoning=_keyword_reasoning(keyword.matched_keywords),
        evidence=_build_evidence(ocr_result, vision),
        guidance_steps=get_guidance_steps(disposal_category, damage_detected),
        analysis_source="keyword",
    )


def _build_from_vision(vision, ocr_result: OcrResult) -> AnalysisResult:
    internal_category = vision.internal_category
    damage_detected = vision.damage_detected

    materials = [
        Material(name=m.name, hazard=m.hazard, confidence=m.confidence)
        for m in vision.materials
        if m.name.strip()
    ]
    if not materials:
        # The model classified the item but listed nothing — use the
        # category knowledge base rather than showing an empty section.
        materials = analyze_materials(internal_category, ocr_result)

    disposal_category = get_disposal_category(internal_category, damage_detected)

    return AnalysisResult(
        item=vision.item,
        category=vision.category_label,
        confidence=vision.confidence,
        materials=materials,
        damage_detected=damage_detected,
        recovery_potential=get_recovery_potential(internal_category),
        disposal_category=disposal_category,
        brand_model=vision.brand_model,
        damage_description=vision.damage_description,
        reasoning=vision.reasoning,
        evidence=_build_evidence(ocr_result, vision),
        guidance_steps=get_guidance_steps(disposal_category, damage_detected),
        analysis_source="vision",
    )


def _build_evidence(ocr_result: OcrResult, vision) -> Evidence:
    f = ocr_result.fields
    certs = [name for name, present in (("FCC", f.fcc), ("CE", f.ce), ("RoHS", f.rohs)) if present]

    chemistry = f.battery_type
    visible_text: Optional[str] = None
    if vision is not None:
        # The label read by the model wins over OCR for chemistry — it's
        # instructed to only report chemistry it can actually see printed.
        chemistry = vision.battery_chemistry or chemistry
        visible_text = vision.visible_text

    return Evidence(
        battery_chemistry=chemistry,
        voltage=f.voltage,
        capacity=f.capacity_mah,
        un_number=f.un_number,
        model_number=f.model_number,
        certifications=certs,
        warnings=f.warnings[:5],
        visible_text=visible_text,
        ocr_text_found=ocr_result.has_useful_text,
    )


def _keyword_reasoning(matched_keywords: List[str]) -> str:
    if not matched_keywords:
        return "Identified from text found on the label."
    shown = ", ".join(f'"{k}"' for k in matched_keywords[:4])
    return f"Identified from label text matching {shown}."
