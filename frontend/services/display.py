"""Display labels and local fallback guidance.

Display maps turn contract enum values (snake_case / lowercase) into
user-facing labels. The guidance steps here are a FALLBACK only: the backend
now returns `guidance_steps` and the dashboard prefers those. These are kept
so the UI still renders sensible steps against an older backend or the mock.
"""

from models.result import AnalysisResult

SAFETY_DISCLAIMER = (
    "LabelWise provides AI-assisted guidance and cannot chemically verify materials "
    "or replace manufacturer/waste-authority/professional instructions. "
    "If an item appears damaged, leaking, swollen, or burning, prioritize personal safety "
    "and contact an appropriate local authority or emergency service."
)

DAMAGED_BATTERY_WARNINGS = [
    "Do NOT puncture, compress, crush, or bend the item",
    "Do NOT open, disassemble, or attempt repair",
    "Do NOT charge it or connect it to power",
    "Keep away from heat, flames, and flammable materials",
    "Contact a hazardous/e-waste service immediately",
]

_GUIDANCE_BY_DISPOSAL = {
    "battery_recycling": [
        "Do not place in regular household trash",
        "Tape the terminals to prevent short circuits",
        "Store in a cool, dry place until you can drop it off",
        "Take to a battery recycling drop-off point",
    ],
    "e_waste": [
        "Do not place in regular household trash",
        "Back up and remove any personal data if possible",
        "Check if the manufacturer offers a take-back program",
        "Take to an e-waste collection facility",
    ],
    "hazardous_waste": [
        "Do not place in regular household trash",
        "Do not puncture, crush, or open the item",
        "Keep away from heat, water, and other chemicals",
        "Contact your local hazardous-waste disposal service",
    ],
    "specialized_recycling": [
        "Do not place in regular household trash",
        "Contact a specialized e-waste recycler",
        "Some components may contain recoverable precious metals",
    ],
    "general_recyclable": [
        "Rinse/clean if needed",
        "Place in your regular recycling bin if accepted locally",
        "Check local recycling guidelines for specific rules",
    ],
    "reuse_refurbishment": [
        "Test if the device still functions",
        "Consider donating, selling, or giving it away",
        "Look into repair options before recycling",
    ],
    "unknown": [
        "Do not place in regular household trash",
        "Check the item for any labels or markings",
        "Search for local e-waste drop-off options",
    ],
}


def get_guidance_steps(result: AnalysisResult) -> list[str]:
    """Backend-provided steps if present; otherwise the local fallback."""
    if result.guidance_steps:
        return list(result.guidance_steps)
    if result.damage_detected:
        return list(DAMAGED_BATTERY_WARNINGS)
    return list(_GUIDANCE_BY_DISPOSAL.get(
        result.disposal_category,
        ["Do not place in regular household trash", "Check with your local waste authority for guidance"],
    ))


HAZARD_DISPLAY = {
    "critical": "CRITICAL",
    "high": "HIGH",
    "medium": "MEDIUM",
    "low": "LOW",
    "unknown": "UNKNOWN",
}

MATERIAL_CONFIDENCE_DISPLAY = {
    "high": "High confidence",
    "medium": "Likely",
    "low": "Possible",
}

RECOVERY_DISPLAY = {
    "high": "HIGH",
    "moderate": "MODERATE",
    "low": "LOW",
    "unknown": "UNKNOWN",
}

RECOVERY_HINT = {
    "high": "Contains valuable recoverable metals or components",
    "moderate": "Some recoverable materials",
    "low": "Little recoverable value — recycle for safety, not value",
    "unknown": "Recovery value could not be determined",
}

DISPOSAL_DISPLAY = {
    "battery_recycling": "Battery Recycling",
    "e_waste": "E-Waste",
    "hazardous_waste": "Hazardous Waste",
    "specialized_recycling": "Specialized Recycling",
    "general_recyclable": "General Recyclable",
    "reuse_refurbishment": "Reuse / Refurbishment",
    "unknown": "Unknown",
}

DISPOSAL_ICON = {
    "battery_recycling": "🔋",
    "e_waste": "💻",
    "hazardous_waste": "☣️",
    "specialized_recycling": "🔬",
    "general_recyclable": "♻️",
    "reuse_refurbishment": "🔁",
    "unknown": "❓",
}
