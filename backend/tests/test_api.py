"""
HTTP-level tests for POST /analyze and GET /health via FastAPI's TestClient.

These run WITHOUT Tesseract and WITHOUT an Anthropic credential: the OCR and
vision stages are monkeypatched so the tests exercise the route wiring,
fallback logic, error contract, and safety overrides deterministically.

Run from the `labelwise/` directory:
    pytest backend/tests -v
"""

import os
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.main import app
from backend.services import pipeline
from backend.services.ocr_service import OcrFields, OcrResult
from backend.services.vision_classifier import VisionMaterial, VisionResult

client = TestClient(app)

POOR_QUALITY = "We can't confidently analyze this image. Please upload a clearer photo."
TOO_LARGE = "This image exceeds the 5 MB upload limit."
UNSUPPORTED = "This file type isn't supported. Please upload JPG, PNG, or WEBP."


def _png_bytes(size=(200, 120)) -> bytes:
    img = Image.new("RGB", size, color=(200, 200, 200))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _post(data: bytes, filename="item.png", content_type="image/png"):
    return client.post("/analyze", files={"file": (filename, data, content_type)})


def _ocr(text: str, battery_type=None) -> OcrResult:
    fields = OcrFields(battery_type=battery_type)
    return OcrResult(raw_text=text, fields=fields, has_useful_text=len(text) >= 3)


def _vision(category="Power Bank", confidence=0.93, damage=False, materials=None, chemistry="lithium-ion"):
    return VisionResult(
        internal_category=category,
        item="Power Bank" if category == "Power Bank" else category,
        category_label="Battery Electronics" if category == "Power Bank" else category,
        brand_model="Anker PowerCore",
        confidence=confidence,
        reasoning="Label reads 'Power Bank 10000mAh'.",
        materials=materials
        if materials is not None
        else [
            VisionMaterial(name="Lithium-ion battery", hazard="high", confidence="high"),
            VisionMaterial(name="Plastic housing", hazard="low", confidence="medium"),
        ],
        damage_detected=damage,
        damage_description="Visible swelling of the casing" if damage else None,
        battery_chemistry=chemistry,
        visible_text="Power Bank 10000mAh Li-ion",
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health_reports_vision_flag(monkeypatch):
    monkeypatch.setattr(pipeline.vision_classifier, "provider", lambda: None)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "vision_enabled": False, "vision_provider": None}

    monkeypatch.setattr(pipeline.vision_classifier, "provider", lambda: "gemini")
    assert client.get("/health").json() == {"status": "ok", "vision_enabled": True, "vision_provider": "gemini"}


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

def _clear_vision_env(monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "GEMINI_API_KEY", "GOOGLE_API_KEY",
              "LABELWISE_VISION_PROVIDER", "LABELWISE_VISION_ENABLED"):
        monkeypatch.delenv(k, raising=False)
    # Ignore any `ant auth login` profile on the dev machine.
    monkeypatch.setattr(pipeline.vision_classifier, "_has_anthropic_credential",
                        lambda: bool(os.environ.get("ANTHROPIC_API_KEY")))


def test_provider_auto_prefers_claude_then_gemini(monkeypatch):
    vc = pipeline.vision_classifier
    _clear_vision_env(monkeypatch)
    assert vc.provider() is None

    monkeypatch.setenv("GEMINI_API_KEY", "g")
    assert vc.provider() == "gemini"

    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    assert vc.provider() == "claude"


def test_provider_can_be_forced_or_disabled(monkeypatch):
    vc = pipeline.vision_classifier
    _clear_vision_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("GEMINI_API_KEY", "g")

    monkeypatch.setenv("LABELWISE_VISION_PROVIDER", "gemini")
    assert vc.provider() == "gemini"

    monkeypatch.setenv("LABELWISE_VISION_PROVIDER", "off")
    assert vc.provider() is None

    monkeypatch.setenv("LABELWISE_VISION_PROVIDER", "auto")
    monkeypatch.setenv("LABELWISE_VISION_ENABLED", "0")
    assert vc.provider() is None


# ---------------------------------------------------------------------------
# Validation / error contract
# ---------------------------------------------------------------------------

def test_unsupported_extension_returns_error_contract():
    r = _post(_png_bytes(), filename="item.gif", content_type="image/gif")
    assert r.status_code == 422
    assert r.json() == {"error": True, "message": UNSUPPORTED}


def test_spoofed_extension_is_caught_by_decode():
    r = _post(b"definitely not an image", filename="item.png")
    assert r.status_code == 422
    assert r.json()["message"] == UNSUPPORTED


def test_oversized_declared_body_rejected_before_parsing():
    # A lying Content-Length must be refused by the middleware with the
    # exact PRD message, not a raw 413.
    r = client.post(
        "/analyze",
        content=b"x",
        headers={"content-type": "multipart/form-data; boundary=abc", "content-length": str(50 * 1024 * 1024)},
    )
    assert r.status_code == 422
    assert r.json() == {"error": True, "message": TOO_LARGE}


def test_oversized_actual_body_rejected_by_capped_read():
    big = _png_bytes() + b"\x00" * (5 * 1024 * 1024 + 10)
    r = _post(big)
    assert r.status_code == 422
    assert r.json()["message"] == TOO_LARGE


# ---------------------------------------------------------------------------
# Vision path
# ---------------------------------------------------------------------------

def test_vision_result_drives_full_response(monkeypatch):
    monkeypatch.setattr(pipeline, "run_ocr", lambda img: _ocr("POWER BANK 10000mAh Li-ion", "lithium-ion"))
    monkeypatch.setattr(pipeline.vision_classifier, "classify", lambda img, ocr: _vision())

    r = _post(_png_bytes())
    assert r.status_code == 200
    body = r.json()

    assert body["item"] == "Power Bank"
    assert body["category"] == "Battery Electronics"
    assert body["confidence"] == 0.93
    assert body["analysis_source"] == "vision"
    assert body["brand_model"] == "Anker PowerCore"
    assert body["reasoning"]
    assert body["damage_detected"] is False
    assert body["disposal_category"] == "battery_recycling"
    assert body["recovery_potential"] == "moderate"
    assert body["materials"][0] == {"name": "Lithium-ion battery", "hazard": "high", "confidence": "high"}
    assert body["evidence"]["battery_chemistry"] == "lithium-ion"
    assert body["evidence"]["visible_text"] == "Power Bank 10000mAh Li-ion"
    assert body["evidence"]["ocr_text_found"] is True
    assert body["guidance_steps"] and "Tape the terminals" in " ".join(body["guidance_steps"])


def test_vision_damage_escalates_to_hazardous_waste_with_damage_steps(monkeypatch):
    monkeypatch.setattr(pipeline, "run_ocr", lambda img: _ocr(""))
    monkeypatch.setattr(pipeline.vision_classifier, "classify", lambda img, ocr: _vision(damage=True))

    body = _post(_png_bytes()).json()
    assert body["damage_detected"] is True
    assert body["damage_description"] == "Visible swelling of the casing"
    # PRD §2.8 — Safety > Disposal, enforced in code regardless of category.
    assert body["disposal_category"] == "hazardous_waste"
    assert any("Do NOT puncture" in s for s in body["guidance_steps"])


def test_vision_with_empty_materials_falls_back_to_knowledge_base(monkeypatch):
    monkeypatch.setattr(pipeline, "run_ocr", lambda img: _ocr(""))
    monkeypatch.setattr(pipeline.vision_classifier, "classify", lambda img, ocr: _vision(materials=[]))

    body = _post(_png_bytes()).json()
    names = [m["name"] for m in body["materials"]]
    assert "Lithium-ion battery" in names and "Copper" in names


# ---------------------------------------------------------------------------
# Keyword fallback path
# ---------------------------------------------------------------------------

def test_keyword_fallback_when_vision_unavailable(monkeypatch):
    monkeypatch.setattr(pipeline, "run_ocr", lambda img: _ocr("Portable Charger Model X1 Output 5V"))
    monkeypatch.setattr(pipeline.vision_classifier, "classify", lambda img, ocr: None)

    body = _post(_png_bytes()).json()
    assert body["analysis_source"] == "keyword"
    assert body["item"] == "Power Bank"
    assert "portable charger" in body["reasoning"]
    assert body["evidence"]["ocr_text_found"] is True
    assert body["guidance_steps"]


def test_keyword_fallback_when_vision_says_unknown_but_label_is_readable(monkeypatch):
    unknown = _vision(category=None, confidence=0.2)
    unknown.internal_category = None
    monkeypatch.setattr(pipeline, "run_ocr", lambda img: _ocr("laptop notebook computer"))
    monkeypatch.setattr(pipeline.vision_classifier, "classify", lambda img, ocr: unknown)

    body = _post(_png_bytes()).json()
    assert body["analysis_source"] == "keyword"
    assert body["item"] == "Laptop"


def test_vision_unknown_and_no_text_returns_poor_quality(monkeypatch):
    unknown = _vision(category=None, confidence=0.1)
    unknown.internal_category = None
    monkeypatch.setattr(pipeline, "run_ocr", lambda img: _ocr(""))
    monkeypatch.setattr(pipeline.vision_classifier, "classify", lambda img, ocr: unknown)

    r = _post(_png_bytes())
    assert r.status_code == 422
    assert r.json() == {"error": True, "message": POOR_QUALITY}


def test_unexpected_exception_returns_generic_message(monkeypatch):
    def boom(img, ocr):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(pipeline, "run_ocr", lambda img: _ocr("power bank"))
    monkeypatch.setattr(pipeline.vision_classifier, "classify", boom)

    # TestClient re-raises server exceptions by default; we want to see what
    # a real client sees — the global handler's JSON, not a traceback.
    quiet = TestClient(app, raise_server_exceptions=False)
    r = quiet.post("/analyze", files={"file": ("item.png", _png_bytes(), "image/png")})
    assert r.status_code == 500
    assert r.json() == {"error": True, "message": "LabelWise couldn't complete the analysis. Please try again."}
