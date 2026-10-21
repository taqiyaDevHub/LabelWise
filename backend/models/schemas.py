"""
LabelWise — Canonical response schemas.

This file is the SINGLE SOURCE OF TRUTH for the backend<->frontend contract.
Do NOT rename or remove fields here without agreeing with the frontend
teammate first — the Streamlit service layer expects exactly this shape.

The original 7 fields (item, category, confidence, materials, damage_detected,
recovery_potential, disposal_category) are unchanged. Everything added on top
is OPTIONAL with a default, so an older frontend that only knows the 7-field
shape keeps working, and the frontend's from_dict() tolerates their absence.

Canonical success shape:
{
  "item": "Power Bank",
  "category": "Battery Electronics",
  "confidence": 0.94,
  "materials": [
    {"name": "Lithium-ion battery", "hazard": "high", "confidence": "high"},
    {"name": "Copper", "hazard": "low", "confidence": "medium"}
  ],
  "damage_detected": false,
  "recovery_potential": "moderate",
  "disposal_category": "battery_recycling",

  "brand_model": "Anker PowerCore 10000",       # optional
  "damage_description": null,                   # optional, set when damage_detected
  "reasoning": "Label reads 'Power Bank 10000mAh, Li-ion' ...",  # the "Why?"
  "evidence": {                                 # what was actually observed
    "battery_chemistry": "lithium-ion",
    "voltage": "3.7V",
    "capacity": "10000mAh",
    "un_number": "UN3481",
    "model_number": "A1263",
    "certifications": ["CE", "FCC", "RoHS"],
    "warnings": ["Do not disassemble"],
    "visible_text": "...",
    "ocr_text_found": true
  },
  "guidance_steps": ["Tape the terminals", ...],
  "analysis_source": "vision"                   # "vision" | "keyword"
}

Canonical error shape (agreed separately, kept apart from the success schema):
{
  "error": true,
  "message": "<one of the exact PRD-defined user-facing strings>"
}
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


# hazard is lowercase per the canonical example — keep it that way everywhere.
HazardLevel = Literal["low", "medium", "high", "critical", "unknown"]

# Per-material confidence (PRD: High/Medium/Low per material).
MaterialConfidence = Literal["high", "medium", "low"]

RecoveryPotential = Literal["low", "moderate", "high", "unknown"]

DisposalCategory = Literal[
    "general_recyclable",
    "e_waste",
    "battery_recycling",
    "hazardous_waste",
    "specialized_recycling",
    "reuse_refurbishment",
    "unknown",
]

AnalysisSource = Literal["vision", "keyword"]


class Material(BaseModel):
    name: str
    hazard: HazardLevel
    confidence: Optional[MaterialConfidence] = None


class Evidence(BaseModel):
    """What LabelWise actually observed — the explainability block.

    Every field is optional; an empty Evidence is valid and means "nothing
    structured was read off the label". The frontend renders whatever is
    present.
    """

    battery_chemistry: Optional[str] = None
    voltage: Optional[str] = None
    capacity: Optional[str] = None
    un_number: Optional[str] = None
    model_number: Optional[str] = None
    certifications: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    visible_text: Optional[str] = None
    ocr_text_found: bool = False


class AnalysisResult(BaseModel):
    """The canonical success response. The first 7 fields are fixed."""

    item: str
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    materials: List[Material]
    damage_detected: bool
    recovery_potential: RecoveryPotential
    disposal_category: DisposalCategory

    # --- Additive fields (all optional with defaults) ---
    brand_model: Optional[str] = None
    damage_description: Optional[str] = None
    reasoning: Optional[str] = None
    evidence: Evidence = Field(default_factory=Evidence)
    guidance_steps: List[str] = Field(default_factory=list)
    analysis_source: AnalysisSource = "keyword"


class ErrorResponse(BaseModel):
    """Fixed minimal error shape — separate from AnalysisResult.

    message must be one of the exact PRD-defined user-facing strings:
      - "This file type isn't supported. Please upload JPG, PNG, or WEBP."
      - "This image exceeds the 5 MB upload limit."
      - "We can't confidently analyze this image. Please upload a clearer photo."
      - "LabelWise couldn't complete the analysis. Please try again."
    """

    error: Literal[True] = True
    message: str


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    vision_enabled: bool = False
    vision_provider: Optional[str] = None  # "claude" | "gemini" | None
