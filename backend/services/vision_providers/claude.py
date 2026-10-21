"""Anthropic provider — Claude with structured outputs.

Credential: ANTHROPIC_API_KEY (or an `ant auth login` profile).
Tuning:     LABELWISE_VISION_MODEL   (default claude-opus-5)
            LABELWISE_VISION_EFFORT  low | medium | high (default medium)
            LABELWISE_VISION_TIMEOUT seconds (default 45)
"""

import base64
import logging
import os
from typing import Optional

from PIL import Image

from backend.services.ocr_service import OcrResult
from backend.services.vision_classifier import (
    SYSTEM_PROMPT,
    VisionAnalysis,
    image_to_jpeg_bytes,
    user_prompt,
)

logger = logging.getLogger("labelwise.vision.claude")

MODEL_ID = os.environ.get("LABELWISE_VISION_MODEL", "claude-opus-5")
# Effort trades latency for thoroughness. "medium" keeps a single-image
# classification comfortably inside the PRD's ~15s analysis target; raise to
# "high" if damage-detection recall matters more than speed.
EFFORT = os.environ.get("LABELWISE_VISION_EFFORT", "medium")
REQUEST_TIMEOUT_SECONDS = float(os.environ.get("LABELWISE_VISION_TIMEOUT", "45"))

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic  # lazy so the keyword-only path has no SDK dependency

        _client = anthropic.Anthropic(timeout=REQUEST_TIMEOUT_SECONDS, max_retries=1)
    return _client


def analyze(display_image: Image.Image, ocr_result: Optional[OcrResult]) -> Optional[VisionAnalysis]:
    import anthropic

    try:
        client = _get_client()
        response = client.messages.parse(
            model=MODEL_ID,
            max_tokens=4096,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": EFFORT},
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": base64.standard_b64encode(image_to_jpeg_bytes(display_image)).decode("utf-8"),
                        },
                    },
                    {"type": "text", "text": user_prompt(ocr_result)},
                ],
            }],
            output_format=VisionAnalysis,
        )
    except anthropic.RateLimitError:
        logger.warning("Claude rate-limited; falling back to keyword path")
        return None
    except anthropic.APIStatusError as e:
        logger.warning("Claude API error %s: %s", e.status_code, e.message)
        return None
    except anthropic.APIConnectionError as e:
        logger.warning("Claude connection error: %s", e)
        return None

    if response.stop_reason == "refusal":
        logger.warning("Claude refused the request")
        return None

    parsed: Optional[VisionAnalysis] = response.parsed_output
    if parsed is None:
        logger.warning("Claude returned no parsable output (stop_reason=%s)", response.stop_reason)
    return parsed
