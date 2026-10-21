"""Frontend result model — mirrors backend/models/schemas.py.

The first 7 fields are the fixed canonical contract. Everything after them
is optional: from_dict() tolerates their absence, so the UI works against an
older backend that only sends the 7-field shape.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MaterialEntry:
    name: str
    hazard: str
    confidence: Optional[str] = None  # "high" | "medium" | "low" | None


@dataclass
class Evidence:
    battery_chemistry: Optional[str] = None
    voltage: Optional[str] = None
    capacity: Optional[str] = None
    un_number: Optional[str] = None
    model_number: Optional[str] = None
    certifications: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    visible_text: Optional[str] = None
    ocr_text_found: bool = False

    def has_label_facts(self) -> bool:
        return any([
            self.battery_chemistry, self.voltage, self.capacity, self.un_number,
            self.model_number, self.certifications, self.warnings,
        ])

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "Evidence":
        data = data or {}
        return cls(
            battery_chemistry=data.get("battery_chemistry"),
            voltage=data.get("voltage"),
            capacity=data.get("capacity"),
            un_number=data.get("un_number"),
            model_number=data.get("model_number"),
            certifications=list(data.get("certifications") or []),
            warnings=list(data.get("warnings") or []),
            visible_text=data.get("visible_text"),
            ocr_text_found=bool(data.get("ocr_text_found", False)),
        )


@dataclass
class AnalysisResult:
    item: str
    category: str
    confidence: float
    materials: List[MaterialEntry]
    damage_detected: bool
    recovery_potential: str
    disposal_category: str

    brand_model: Optional[str] = None
    damage_description: Optional[str] = None
    reasoning: Optional[str] = None
    evidence: Evidence = field(default_factory=Evidence)
    guidance_steps: List[str] = field(default_factory=list)
    analysis_source: str = "keyword"

    @property
    def is_unknown(self) -> bool:
        return self.item.lower() in ("unknown", "unknown item") or self.confidence < 0.5

    def to_dict(self) -> dict:
        return {
            "item": self.item,
            "category": self.category,
            "confidence": self.confidence,
            "materials": [
                {"name": m.name, "hazard": m.hazard, "confidence": m.confidence} for m in self.materials
            ],
            "damage_detected": self.damage_detected,
            "recovery_potential": self.recovery_potential,
            "disposal_category": self.disposal_category,
            "brand_model": self.brand_model,
            "damage_description": self.damage_description,
            "reasoning": self.reasoning,
            "evidence": self.evidence.__dict__,
            "guidance_steps": list(self.guidance_steps),
            "analysis_source": self.analysis_source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AnalysisResult":
        materials = [
            MaterialEntry(name=m["name"], hazard=m["hazard"], confidence=m.get("confidence"))
            for m in data.get("materials", [])
        ]
        return cls(
            item=data["item"],
            category=data["category"],
            confidence=data["confidence"],
            materials=materials,
            damage_detected=data["damage_detected"],
            recovery_potential=data["recovery_potential"],
            disposal_category=data["disposal_category"],
            brand_model=data.get("brand_model"),
            damage_description=data.get("damage_description"),
            reasoning=data.get("reasoning"),
            evidence=Evidence.from_dict(data.get("evidence")),
            guidance_steps=list(data.get("guidance_steps") or []),
            analysis_source=data.get("analysis_source", "keyword"),
        )
