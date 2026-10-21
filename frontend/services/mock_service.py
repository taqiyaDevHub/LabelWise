"""Mock analysis service for demo/development.

Used when LABELWISE_USE_MOCK=1 — lets the UI be demoed on a machine with no
backend (or no Tesseract / API key). Returns canned results keyed off the
uploaded filename so every UI state can be shown.
"""

import time

from models.result import AnalysisResult, Evidence, MaterialEntry
from services.analysis_service import AnalysisError, AnalysisService

ERR_POOR_QUALITY = "We can't confidently analyze this image. Please upload a clearer photo."
ERR_ANALYSIS_FAILURE = "LabelWise couldn't complete the analysis. Please try again."


class MockAnalysisService(AnalysisService):
    """Mock service for demo/development. Returns different results based on filename
    to demonstrate all UI states without a real backend.

    Filename triggers (demo only):
      - contains 'blurry', 'dark', or 'poor' → poor image quality error
      - contains 'fail' or 'error' → analysis failure error
      - contains 'unknown' or 'random' → low-confidence unknown result
      - contains 'damage' or 'swollen' → damaged battery result
      - anything else → power bank success (PRD golden path)
    """

    def analyze_image(self, image_bytes: bytes, filename: str) -> AnalysisResult:
        name = filename.lower()
        # A real analysis takes a few seconds; pause so the in-flight UI
        # (scanner) is actually visible when demoing without a backend.
        time.sleep(2.2)

        if any(kw in name for kw in ("blurry", "dark", "poor")):
            raise AnalysisError(ERR_POOR_QUALITY)

        if any(kw in name for kw in ("fail", "error")):
            raise AnalysisError(ERR_ANALYSIS_FAILURE)

        if any(kw in name for kw in ("unknown", "random")):
            return self._unknown_result()

        if any(kw in name for kw in ("damage", "swollen")):
            return self._damaged_battery_result()

        return self._power_bank_result()

    def _power_bank_result(self) -> AnalysisResult:
        return AnalysisResult(
            item="Power Bank",
            category="Battery Electronics",
            confidence=0.94,
            materials=[
                MaterialEntry(name="Lithium-ion battery", hazard="high", confidence="high"),
                MaterialEntry(name="Circuit board (PCB)", hazard="medium", confidence="medium"),
                MaterialEntry(name="Copper", hazard="low", confidence="medium"),
                MaterialEntry(name="Plastic housing", hazard="low", confidence="high"),
            ],
            damage_detected=False,
            recovery_potential="moderate",
            disposal_category="battery_recycling",
            brand_model="Anker PowerCore 10000",
            reasoning="The label reads 'Power Bank 10000mAh' with a Li-ion marking and USB output ratings, "
                      "and the slim rectangular form with USB ports matches a portable charger.",
            evidence=Evidence(
                battery_chemistry="lithium-ion",
                voltage="3.7V",
                capacity="10000mAh",
                un_number="UN3481",
                model_number="A1263",
                certifications=["CE", "FCC", "RoHS"],
                warnings=["Do not disassemble", "Keep away from fire"],
                visible_text=(
                    "Anker PowerCore 10000\n"
                    "Model A1263\n"
                    "Li-ion 3.7V 10000mAh / 37Wh\n"
                    "Input 5V=2A  Output 5V=2.4A\n"
                    "UN3481"
                ),
                ocr_text_found=True,
            ),
            analysis_source="vision",
        )

    def _unknown_result(self) -> AnalysisResult:
        return AnalysisResult(
            item="Unknown Item",
            category="Unknown",
            confidence=0.15,
            materials=[],
            damage_detected=False,
            recovery_potential="unknown",
            disposal_category="unknown",
            reasoning="The image is too dark and the object is partially out of frame; no label or "
                      "distinguishing shape is visible.",
            analysis_source="vision",
        )

    def _damaged_battery_result(self) -> AnalysisResult:
        return AnalysisResult(
            item="Power Bank",
            category="Battery Electronics",
            confidence=0.88,
            materials=[
                MaterialEntry(name="Lithium-ion battery", hazard="high", confidence="high"),
                MaterialEntry(name="Circuit board (PCB)", hazard="medium", confidence="medium"),
                MaterialEntry(name="Plastic housing", hazard="low", confidence="high"),
            ],
            damage_detected=True,
            recovery_potential="low",
            disposal_category="hazardous_waste",
            damage_description="The casing is visibly bulging on one side and the seam has split open, "
                               "exposing the battery cell.",
            reasoning="Rectangular power bank with USB ports and a Li-ion marking; the swollen casing "
                      "indicates a compromised lithium cell.",
            evidence=Evidence(battery_chemistry="lithium-ion", capacity="20000mAh", ocr_text_found=True),
            analysis_source="vision",
        )
