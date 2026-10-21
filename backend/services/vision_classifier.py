"""
Vision classifier — PRD FR-04 (item classification), FR-05/FR-06 (materials,
hazards, per-material confidence), FR-09 (confidence), §2.8 (damage
detection), SHOULD-priority "Why?" explainability.

Sends the preprocessed photo to a vision model with a strict JSON output
schema and gets back, in ONE call: what the item is, how sure it is and why,
the materials it can see (with per-material confidence), and whether the
item shows visible damage (swelling, corrosion, leaking, burn marks, cracked
cells). OCR text from the previous stage is passed along as a hint so label
markings (chemistry, UN numbers, model numbers) reinforce the visual read.

Provider-agnostic core. The prompt, the output schema, the result type and
the "is it unknown?" policy live here; the actual API call lives in one
small module per provider:

    vision_providers/claude.py   Anthropic  (ANTHROPIC_API_KEY)
    vision_providers/gemini.py   Google     (GEMINI_API_KEY) — has a free tier

Selection (LABELWISE_VISION_PROVIDER):
    auto    (default) claude if an Anthropic credential exists, else gemini
                      if a Gemini key exists, else vision is off
    claude / gemini   force that provider
    off               keyword-only mode (same as LABELWISE_VISION_ENABLED=0)

What this module deliberately does NOT decide:
  - disposal_category  -> disposal_engine.py (deterministic, damage override
                          enforced in code — "rules govern safety")
  - recovery_potential -> recovery_engine.py (category-based only)
The model classifies; the rules engines still govern safety guidance.

When the provider is unavailable — or the call fails for any reason —
classify() returns None and the route falls back to the deterministic
keyword classifier, so the demo never hard-depends on the network.
"""

import json
import logging
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import List, Literal, Optional

from PIL import Image
from pydantic import BaseModel

from backend.services.ocr_service import OcrResult

logger = logging.getLogger("labelwise.vision")

_PRODUCTS_PATH = Path(__file__).resolve().parent.parent / "data" / "products.json"

# Below this, the model's own read is treated as "not confident enough" and
# the route falls through to the keyword path / uncertainty response.
MIN_VISION_CONFIDENCE = 0.35


def _load_products() -> dict:
    with open(_PRODUCTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["categories"]


# The internal taxonomy (PRD v1.1 §2.3) — same keys products.json,
# materials.json, disposal_rules.json and recovery_rules.json use, so a
# vision result plugs straight into the existing rules engines.
_PRODUCTS = _load_products()
CATEGORY_KEYS: List[str] = list(_PRODUCTS.keys())

CategoryLiteral = Literal[
    "Power Bank", "Phone", "Laptop", "Charger", "Cable", "PCB", "Monitor", "TV",
    "Printer", "Component", "Small Appliance", "Packaging", "Battery", "Unknown",
]


# ---------------------------------------------------------------------------
# Structured output schema — what we ask the model to return. Shared by all
# providers so the rest of the pipeline never knows which one answered.
# ---------------------------------------------------------------------------

class VisionMaterial(BaseModel):
    name: str
    hazard: Literal["low", "medium", "high", "critical", "unknown"]
    confidence: Literal["high", "medium", "low"]


class VisionAnalysis(BaseModel):
    is_electronic_or_recyclable_item: bool
    category: CategoryLiteral
    item_name: str
    brand_model: Optional[str]
    confidence: float
    reasoning: str
    materials: List[VisionMaterial]
    damage_detected: bool
    damage_description: Optional[str]
    battery_chemistry: Optional[
        Literal["lithium-ion", "lithium-polymer", "nimh", "nicd", "lead-acid", "alkaline"]
    ]
    visible_text: Optional[str]


@dataclass
class VisionResult:
    internal_category: Optional[str]  # None => unknown
    item: str
    category_label: str
    brand_model: Optional[str]
    confidence: float
    reasoning: str
    materials: List[VisionMaterial]
    damage_detected: bool
    damage_description: Optional[str]
    battery_chemistry: Optional[str]
    visible_text: Optional[str]

    @property
    def is_unknown(self) -> bool:
        return self.internal_category is None


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the vision analysis stage of LabelWise, an e-waste and recycling item inspector. \
You are shown one photo of a physical item (often an electronic device, a battery, a cable, or its \
product label) and you return a structured assessment.

Categories (choose exactly one):
- Power Bank: portable battery pack / portable charger
- Phone: smartphone or feature phone
- Laptop: laptop, notebook, MacBook, Chromebook
- Charger: wall charger, AC/DC power adapter, power brick
- Cable: USB / HDMI / Ethernet / charging cable
- PCB: bare printed circuit board, motherboard
- Monitor: computer monitor, LCD/LED display
- TV: television
- Printer: printer, toner or ink cartridge
- Component: RAM, CPU, GPU, hard drive, SSD, other internal computer part
- Small Appliance: hair dryer, kettle, blender, toaster, shaver, similar household electronics
- Packaging: cardboard, shipping box, styrofoam, product packaging
- Battery: standalone battery cell/pack (AA/AAA/coin cell/9V/laptop cell/car battery)
- Unknown: not one of the above, or the image doesn't show enough to tell

Rules:
1. Never invent a classification. If the photo is too blurry, dark, cropped, or shows an unrelated \
object, use "Unknown" with low confidence and say why in reasoning.
2. confidence is 0.0–1.0 and must honestly reflect how sure you are from THIS image. A clear \
product with a readable label can be 0.9+; a plausible guess from shape alone is ~0.5–0.7.
3. reasoning is 1–2 sentences a non-expert can read: what visual/text cues led to the answer.
4. materials: list the materials this item contains based on what you can see and what the \
category typically contains. Use these hazard levels: lithium-ion/lithium-polymer/lead-acid/\
nickel-cadmium batteries = high; PCBs, displays, NiMH batteries = medium; copper, aluminum, plastic, \
glass, cardboard, alkaline batteries = low. Per-material confidence: "high" if clearly visible or \
printed on the label, "medium" if typical for this category, "low" if speculative.
5. battery_chemistry: only set it if the label VISIBLY states it (e.g. "Li-ion", "Li-Po", "NiMH"). \
A photo cannot confirm chemistry from shape alone — leave null otherwise.
6. damage_detected: true ONLY for visible physical damage relevant to safety: swelling/bulging, \
leaking, corrosion on terminals, burn/scorch marks, punctures, cracked or exposed battery cells. \
Scratches, dust, wear, or a dirty surface are NOT damage. When true, damage_description states \
exactly what you see.
7. visible_text: transcribe the important label text you can read (model, ratings, chemistry, \
warnings), or null if none.
8. brand_model: brand and model if readable, else null. Do not guess brands from color or shape.
9. item_name: a short generic name for what the object is (e.g. "Power Bank", "18650 Battery Cell", "Laptop", "USB-C Cable") — 1–4 words, NO brand or model in it; those go in brand_model."""


def user_prompt(ocr_result: Optional[OcrResult]) -> str:
    parts = ["Analyze this item photo and return the structured assessment."]
    if ocr_result is not None and ocr_result.has_useful_text:
        parts.append(
            "For reference, an OCR pass extracted the following text from the image "
            "(may contain errors — trust what you can see over this):\n"
            f"<ocr_text>\n{ocr_result.raw_text[:2000]}\n</ocr_text>"
        )
    return "\n\n".join(parts)


def image_to_jpeg_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

PROVIDERS = ("claude", "gemini")


def _has_anthropic_credential() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    # `ant auth login` stores a profile the SDK reads automatically.
    return (Path.home() / ".config" / "anthropic").exists()


def _has_gemini_credential() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))


def provider() -> Optional[str]:
    """Which provider will answer, or None when vision is off."""
    if os.environ.get("LABELWISE_VISION_ENABLED", "1") == "0":
        return None
    choice = os.environ.get("LABELWISE_VISION_PROVIDER", "auto").strip().lower()
    if choice == "off":
        return None
    if choice in PROVIDERS:
        return choice
    if choice != "auto":
        logger.warning("Unknown LABELWISE_VISION_PROVIDER=%r; using auto", choice)
    if _has_anthropic_credential():
        return "claude"
    if _has_gemini_credential():
        return "gemini"
    return None


def is_enabled() -> bool:
    return provider() is not None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def classify(display_image: Image.Image, ocr_result: Optional[OcrResult]) -> Optional[VisionResult]:
    """Run the vision pass. Returns None when vision is unavailable or the
    call fails — the caller falls back to the keyword classifier."""
    name = provider()
    if name is None:
        return None

    try:
        if name == "claude":
            from backend.services.vision_providers import claude as impl
        else:
            from backend.services.vision_providers import gemini as impl
        parsed = impl.analyze(display_image, ocr_result)
    except Exception:
        # Providers catch and log their own API errors and return None;
        # anything that escapes is a bug in the provider, not the user's
        # photo — still degrade rather than 500.
        logger.exception("Vision provider %s failed unexpectedly", name)
        return None

    if parsed is None:
        return None
    return _to_result(parsed)


def _to_result(parsed: VisionAnalysis) -> VisionResult:
    confidence = round(max(0.0, min(1.0, float(parsed.confidence))), 2)

    unknown = (
        not parsed.is_electronic_or_recyclable_item
        or parsed.category == "Unknown"
        or parsed.category not in CATEGORY_KEYS
        or confidence < MIN_VISION_CONFIDENCE
    )

    return VisionResult(
        internal_category=None if unknown else parsed.category,
        item=parsed.item_name.strip() or parsed.category,
        category_label=_category_label(parsed.category) if not unknown else "Unknown",
        brand_model=(parsed.brand_model or "").strip() or None,
        confidence=confidence,
        reasoning=parsed.reasoning.strip(),
        materials=parsed.materials,
        damage_detected=bool(parsed.damage_detected),
        damage_description=(parsed.damage_description or "").strip() or None,
        battery_chemistry=parsed.battery_chemistry,
        visible_text=(parsed.visible_text or "").strip() or None,
    )


def _category_label(category_key: str) -> str:
    return _PRODUCTS.get(category_key, {}).get("category_label", category_key)
