"""Google Gemini provider — free-tier friendly.

Credential: GEMINI_API_KEY (or GOOGLE_API_KEY) from https://aistudio.google.com
Tuning:     LABELWISE_GEMINI_MODEL    (default gemini-3.6-flash — on the free tier)
            LABELWISE_VISION_TIMEOUT  seconds (default 45)

Uses Gemini's JSON-mode structured output against the same Pydantic schema
Claude uses, so the rest of the pipeline can't tell the providers apart.
The free tier is rate-limited (requests per minute / per day); a 429 here
degrades to the keyword classifier instead of failing the request.
"""

import logging
import os
from typing import Optional

from PIL import Image
from pydantic import ValidationError

from backend.services.ocr_service import OcrResult
from backend.services.vision_classifier import (
    SYSTEM_PROMPT,
    VisionAnalysis,
    image_to_jpeg_bytes,
    user_prompt,
)

logger = logging.getLogger("labelwise.vision.gemini")

MODEL_ID = os.environ.get("LABELWISE_GEMINI_MODEL", "gemini-3.6-flash")
REQUEST_TIMEOUT_MS = int(float(os.environ.get("LABELWISE_VISION_TIMEOUT", "45")) * 1000)

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        _client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS))
    return _client


def analyze(display_image: Image.Image, ocr_result: Optional[OcrResult]) -> Optional[VisionAnalysis]:
    from google.genai import errors, types

    try:
        client = _get_client()
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[
                types.Part.from_bytes(data=image_to_jpeg_bytes(display_image), mime_type="image/jpeg"),
                user_prompt(ocr_result),
            ],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=VisionAnalysis,
                temperature=0.2,
                # We use no tools; this just silences the SDK's AFC advisory.
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
    except errors.ClientError as e:
        # 429 = free-tier quota; 400/403 = bad key or unsupported model.
        logger.warning("Gemini client error %s: %s", getattr(e, "code", "?"), getattr(e, "message", e))
        return None
    except errors.ServerError as e:
        logger.warning("Gemini server error: %s", getattr(e, "message", e))
        return None
    except errors.APIError as e:
        logger.warning("Gemini API error: %s", e)
        return None
    except Exception as e:  # network/timeouts surface as httpx errors, not APIError
        logger.warning("Gemini request failed: %s", e)
        return None

    text = response.text
    if not text:
        # Empty text usually means the safety filter blocked the response.
        logger.warning("Gemini returned no text (prompt_feedback=%s)", getattr(response, "prompt_feedback", None))
        return None

    try:
        return VisionAnalysis.model_validate_json(text)
    except ValidationError as e:
        logger.warning("Gemini output failed schema validation: %s", e)
        return None
