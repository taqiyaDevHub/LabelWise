"""
OCR — PRD FR-03.

Runs Tesseract on the OCR-ready preprocessed image, then pulls out
structured label fields (battery chemistry, voltage, capacity, certification
marks, UN number, input/output ratings, warning text) via keyword/regex
matching. Deterministic on purpose — an LLM here would be slower, harder to
debug under demo pressure, and isn't needed for label text this templated.

If Tesseract is missing/broken this must NOT crash the request — it degrades
to "no useful text", and the classifier stage (next) falls back to
vision-only identification.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

import pytesseract
from PIL import Image


@dataclass
class OcrFields:
    battery_type: Optional[str] = None
    voltage: Optional[str] = None
    capacity_mah: Optional[str] = None
    model_number: Optional[str] = None
    fcc: bool = False
    ce: bool = False
    rohs: bool = False
    un_number: Optional[str] = None
    input_rating: Optional[str] = None
    output_rating: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class OcrResult:
    raw_text: str
    fields: OcrFields
    has_useful_text: bool  # drives the "poor image quality" / uncertainty path (stage 4+)


# Order matters — more specific chemistries first (li-poly before a bare
# "li" match), so the first hit wins.
_BATTERY_TYPE_PATTERNS = [
    (r"li-?\s?po(ly(mer)?)?|lithium[\s-]?polymer", "lithium-polymer"),
    (r"li-?\s?ion|lithium[\s-]?ion", "lithium-ion"),
    (r"ni-?mh|nickel[\s-]?metal[\s-]?hydride", "nimh"),
    (r"ni-?cd|nickel[\s-]?cadmium", "nicd"),
    (r"lead[\s-]?acid", "lead-acid"),
    (r"\balkaline\b", "alkaline"),
]

_VOLTAGE_PATTERN = re.compile(r"\b(\d{1,3}(?:\.\d{1,2})?)\s?v\b", re.IGNORECASE)
_CAPACITY_PATTERN = re.compile(r"\b(\d{2,6})\s?mah\b", re.IGNORECASE)
_UN_NUMBER_PATTERN = re.compile(r"\bun\s?-?\s?(\d{4})\b", re.IGNORECASE)
_INPUT_PATTERN = re.compile(r"input[:\s]+([0-9][0-9.\-–~vadcma\s]{1,20})", re.IGNORECASE)
_OUTPUT_PATTERN = re.compile(r"output[:\s]+([0-9][0-9.\-–~vadcma\s]{1,20})", re.IGNORECASE)
_MODEL_NUMBER_PATTERN = re.compile(r"model[\s:#]*([a-z0-9\-]{3,})", re.IGNORECASE)
_WARNING_KEYWORDS = ("warning", "caution", "danger", "do not", "keep away")

# Below this many alphanumeric characters, treat OCR output as not useful —
# feeds the "poor image quality" uncertainty path rather than a fabricated
# classification.
_MIN_USEFUL_CHARS = 3


def run_ocr(image: Image.Image) -> OcrResult:
    try:
        raw_text = pytesseract.image_to_string(image)
    except Exception:
        raw_text = ""

    raw_text = raw_text.strip()
    fields = _extract_fields(raw_text)
    alnum_chars = sum(c.isalnum() for c in raw_text)
    has_useful_text = alnum_chars >= _MIN_USEFUL_CHARS

    return OcrResult(raw_text=raw_text, fields=fields, has_useful_text=has_useful_text)


def _extract_fields(text: str) -> OcrFields:
    fields = OcrFields()
    lower = text.lower()

    for pattern, label in _BATTERY_TYPE_PATTERNS:
        if re.search(pattern, lower):
            fields.battery_type = label
            break

    if match := _VOLTAGE_PATTERN.search(lower):
        fields.voltage = f"{match.group(1)}V"

    if match := _CAPACITY_PATTERN.search(lower):
        fields.capacity_mah = f"{match.group(1)}mAh"

    if match := _UN_NUMBER_PATTERN.search(lower):
        fields.un_number = f"UN{match.group(1)}"

    fields.fcc = bool(re.search(r"\bfcc\b", lower))
    # CE is matched case-sensitively on the original text: the mark is always
    # printed in capitals, and a lowercase "ce" is far more often an OCR
    # fragment of another word than a certification.
    fields.ce = bool(re.search(r"\bCE\b", text))
    fields.rohs = bool(re.search(r"\brohs\b", lower))

    if match := _INPUT_PATTERN.search(lower):
        fields.input_rating = match.group(1).strip()

    if match := _OUTPUT_PATTERN.search(lower):
        fields.output_rating = match.group(1).strip()

    if match := _MODEL_NUMBER_PATTERN.search(text):  # original case for model numbers
        fields.model_number = match.group(1).strip()

    for line in text.splitlines():
        if any(kw in line.lower() for kw in _WARNING_KEYWORDS):
            stripped = line.strip()
            if stripped:
                fields.warnings.append(stripped)

    return fields
