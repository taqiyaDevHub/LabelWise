"""
Image validation — server-side, per PRD §2.1/§2.2/§3.1/§3.2.

Never trust the frontend's checks alone. Extension and declared MIME type are
easy to spoof, so the real check is #4 below: actually decoding the bytes
with Pillow. That's what catches a renamed .exe or a corrupt file.

Order matters: cheap/fast checks first (size, extension) before the more
expensive decode step.
"""

import io
from dataclasses import dataclass
from typing import Optional

from PIL import Image, UnidentifiedImageError

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_PIL_FORMATS = {"JPEG", "PNG", "WEBP"}

MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB, per PRD §2.1/§3.2
MAX_DIMENSION_PX = 4096  # per PRD §3.2

# Exact PRD-defined user-facing strings (PRD §5). Do not reword these.
UNSUPPORTED_TYPE_MESSAGE = "This file type isn't supported. Please upload JPG, PNG, or WEBP."
TOO_LARGE_MESSAGE = "This image exceeds the 5 MB upload limit."


class ImageValidationError(Exception):
    """Raised with one of the exact PRD-defined user-facing messages."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


@dataclass
class ValidatedImage:
    contents: bytes
    width: int
    height: int
    format: str
    mime_type: str
    size_bytes: int


def validate_image(
    filename: Optional[str],
    declared_content_type: Optional[str],
    contents: bytes,
) -> ValidatedImage:
    # 1. Size check — cheap, do this before decoding anything.
    size_bytes = len(contents)
    if size_bytes == 0 or size_bytes > MAX_SIZE_BYTES:
        raise ImageValidationError(TOO_LARGE_MESSAGE)

    # 2. Extension check (advisory only — spoofable, never trust alone).
    ext = filename.rsplit(".", 1)[-1].lower() if filename and "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ImageValidationError(UNSUPPORTED_TYPE_MESSAGE)

    # 3. Declared MIME check (advisory only — also spoofable).
    if declared_content_type and declared_content_type not in ALLOWED_MIME_TYPES:
        raise ImageValidationError(UNSUPPORTED_TYPE_MESSAGE)

    # 4. Real signature/decodability check. This is the one that actually
    #    protects against a renamed .exe, a corrupt file, or a non-image
    #    payload with a spoofed extension/MIME.
    try:
        probe = Image.open(io.BytesIO(contents))
        probe.verify()  # raises if the file is corrupt or not a real image
        # verify() leaves the handle unusable for further ops — reopen it.
        img = Image.open(io.BytesIO(contents))
        img_format = img.format
        width, height = img.size
    except (UnidentifiedImageError, OSError, ValueError):
        raise ImageValidationError(UNSUPPORTED_TYPE_MESSAGE)

    if img_format not in ALLOWED_PIL_FORMATS:
        raise ImageValidationError(UNSUPPORTED_TYPE_MESSAGE)

    # 5. Dimension check. The PRD (§3.2) groups this under the same
    #    "resource/size limit" concept as the 5MB check and doesn't define a
    #    separate user-facing string, so this intentionally reuses
    #    TOO_LARGE_MESSAGE — decided, not left open.
    if width > MAX_DIMENSION_PX or height > MAX_DIMENSION_PX:
        raise ImageValidationError(TOO_LARGE_MESSAGE)

    return ValidatedImage(
        contents=contents,
        width=width,
        height=height,
        format=img_format,
        mime_type=declared_content_type or f"image/{img_format.lower()}",
        size_bytes=size_bytes,
    )
