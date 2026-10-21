"""
Smoke tests for the OCR -> classify -> materials -> disposal -> recovery
pipeline, covering the PRD v1.1 §7 test matrix. These exercise the service
layer directly (no running server needed), so `pip install -r
requirements.txt` (plus `pytest`) is enough to run them.

Run with:
    pytest tests/ -v
"""

from io import BytesIO

import pytest
import pytesseract
from PIL import Image, ImageDraw, ImageFont


def _tesseract_available() -> bool:
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


# The end-to-end tests below render text and run real OCR on it. Without the
# Tesseract binary they can't exercise anything meaningful, so they're
# skipped (not failed) — the HTTP-level suite in test_api.py covers the route
# wiring with OCR mocked out and runs everywhere.
requires_tesseract = pytest.mark.skipif(
    not _tesseract_available(), reason="Tesseract binary not installed"
)

from backend.services.classifier import classify
from backend.services.disposal_engine import get_disposal_category
from backend.services.image_validator import ImageValidationError, validate_image
from backend.services.material_analyzer import analyze_materials
from backend.services.ocr_service import run_ocr
from backend.services.preprocess import preprocess_image
from backend.services.recovery_engine import get_recovery_potential


def _label_image(text: str, size=(900, 300)) -> Image.Image:
    """Render text onto a blank image so pytesseract has something to read."""
    img = Image.new("L", size, color=255)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28
        )
    except OSError:
        font = ImageFont.load_default()
    y = 10
    for line in text.split("\n"):
        draw.text((10, y), line, fill=0, font=font)
        y += 34
    return img


def _label_image_bytes(text: str, fmt: str = "PNG") -> bytes:
    img = _label_image(text).convert("RGB")
    buf = BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _run_pipeline(text: str):
    """End-to-end through the real OCR/classify/materials/disposal/recovery
    stages, given synthetic label text (mirrors what routes/analyze.py does
    after preprocessing)."""
    ocr_image = _label_image(text)
    ocr_result = run_ocr(ocr_image)
    classification = classify(ocr_result)
    if classification.is_unknown:
        return classification, ocr_result, None, None, None
    materials = analyze_materials(classification.internal_category, ocr_result)
    disposal = get_disposal_category(classification.internal_category, damage_detected=False)
    recovery = get_recovery_potential(classification.internal_category)
    return classification, ocr_result, materials, disposal, recovery


# ---------------------------------------------------------------------------
# PRD test matrix cases
# ---------------------------------------------------------------------------

@requires_tesseract
def test_power_bank_is_battery_recycling_high_hazard():
    cls, _, materials, disposal, recovery = _run_pipeline(
        "Power Bank\nLi-ion 3.7V 2600mAh\nModel: PB-2200"
    )
    assert cls.internal_category == "Power Bank"
    assert disposal == "battery_recycling"
    assert any(m.hazard == "high" for m in materials)
    assert recovery in {"low", "moderate", "high", "unknown"}


@requires_tesseract
def test_phone_is_e_waste():
    cls, _, materials, disposal, recovery = _run_pipeline(
        "Smartphone\nModel: SM-100\nIMEI 123456789012345"
    )
    assert cls.internal_category == "Phone"
    assert disposal == "e_waste"
    assert any(m.hazard == "high" for m in materials)  # battery default


@requires_tesseract
def test_laptop_is_e_waste_high_recovery():
    cls, _, materials, disposal, recovery = _run_pipeline(
        "Laptop Battery Pack\nLithium-Polymer 11.1V\nModel: LB-9910"
    )
    assert cls.internal_category == "Laptop"
    assert disposal == "e_waste"
    assert recovery == "high"


@requires_tesseract
def test_loose_battery_is_battery_recycling():
    cls, _, materials, disposal, recovery = _run_pipeline("Rechargeable Battery\nAA")
    assert cls.internal_category == "Battery"
    assert disposal == "battery_recycling"


@requires_tesseract
def test_pcb_is_specialized_recycling_high_recovery():
    cls, _, materials, disposal, recovery = _run_pipeline("Printed Circuit Board\nRev C")
    assert cls.internal_category == "PCB"
    assert disposal == "specialized_recycling"
    assert recovery == "high"


@requires_tesseract
def test_cable_is_general_recyclable_low_recovery():
    cls, _, materials, disposal, recovery = _run_pipeline("USB Charging Cable\nHigh Speed Data Cable")
    assert cls.internal_category == "Cable"
    assert disposal == "general_recyclable"
    assert recovery == "low"


@requires_tesseract
def test_unrecognized_text_is_unknown():
    cls, _, materials, disposal, recovery = _run_pipeline("asdkj 89234 zzqq random text")
    assert cls.is_unknown is True
    assert cls.internal_category is None


@requires_tesseract
def test_blurry_or_blank_image_has_no_useful_text():
    blank = Image.new("L", (400, 200), color=255)  # nothing drawn -> no OCR text
    ocr_result = run_ocr(blank)
    assert ocr_result.has_useful_text is False
    cls = classify(ocr_result)
    assert cls.is_unknown is True


def test_damage_detected_always_escalates_to_hazardous_waste():
    # Regardless of category, a damaged item must never resolve to a normal
    # disposal path (PRD v1.1 §2.8: Safety > Disposal > Recovery Value).
    for category in ("Power Bank", "Cable", "Packaging", "PCB", None):
        assert get_disposal_category(category, damage_detected=True) == "hazardous_waste"


@requires_tesseract
def test_unknown_category_defaults_are_safe_not_fabricated():
    assert get_disposal_category(None, damage_detected=False) == "unknown"
    assert get_recovery_potential(None) == "unknown"
    assert analyze_materials(None, run_ocr(Image.new("L", (10, 10)))) == []


@requires_tesseract
def test_battery_chemistry_is_only_claimed_when_ocr_detected_it():
    # Generic "battery" keyword match with no chemistry markings -> hazard
    # must stay "unknown", never a guessed chemistry (PRD FR-11 / §2.5).
    cls, ocr_result, materials, _, _ = _run_pipeline("Battery\nUnlabeled cell")
    assert cls.internal_category == "Battery"
    assert ocr_result.fields.battery_type is None
    battery_material = materials[0]
    assert battery_material.hazard == "unknown"

    # Same category, but OCR *did* detect a chemistry -> specific hazard used.
    cls2, ocr_result2, materials2, _, _ = _run_pipeline("Battery\nNiCd 1.2V")
    assert ocr_result2.fields.battery_type == "nicd"
    assert materials2[0].hazard == "high"


# ---------------------------------------------------------------------------
# Validation / error-path cases (PRD §2.1 / §3.1 / §3.2 / §19)
# ---------------------------------------------------------------------------

def test_valid_png_passes_validation():
    contents = _label_image_bytes("Power Bank\nLi-ion 3.7V", fmt="PNG")
    validated = validate_image(filename="label.png", declared_content_type="image/png", contents=contents)
    assert validated.format == "PNG"


def test_oversized_file_is_rejected():
    huge = b"0" * (5 * 1024 * 1024 + 1)
    with pytest.raises(ImageValidationError):
        validate_image(filename="label.png", declared_content_type="image/png", contents=huge)


def test_unsupported_extension_is_rejected():
    contents = _label_image_bytes("Power Bank", fmt="PNG")
    with pytest.raises(ImageValidationError):
        validate_image(filename="label.exe", declared_content_type="image/png", contents=contents)


def test_corrupt_file_with_spoofed_extension_is_rejected():
    fake_image = b"this is not actually image data" * 10
    with pytest.raises(ImageValidationError):
        validate_image(filename="label.png", declared_content_type="image/png", contents=fake_image)


def test_preprocess_handles_valid_image_without_crashing():
    contents = _label_image_bytes("Power Bank\nLi-ion 3.7V 2600mAh", fmt="PNG")
    result = preprocess_image(contents)
    assert result.width > 0 and result.height > 0
    assert result.ocr_image.mode == "L"
