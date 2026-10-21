"""
Image preprocessing — PRD FR-02.

Produces two things from the validated upload:
  - a resized "display" image (RGB) — for the classification/vision step
  - an OCR-ready image (grayscale, autocontrast, denoised, sharpened)

OCR accuracy depends heavily on this step, so it's deliberate rather than
stacking every filter "just in case" — over-processing (too much sharpening,
too much denoise) can hurt OCR as much as under-processing.
"""

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageFilter, ImageOps

# Cap the working resolution. OCR/vision steps don't need more than this,
# and it keeps everything downstream fast and memory-safe regardless of how
# large the original upload was (up to the validator's 4096px cap).
MAX_WORKING_DIMENSION = 1600


@dataclass
class PreprocessedImage:
    display_image: Image.Image  # RGB, resized — for classification/vision
    ocr_image: Image.Image  # grayscale, enhanced — for OCR
    width: int
    height: int


def _resize_if_needed(img: Image.Image, max_dim: int = MAX_WORKING_DIMENSION) -> Image.Image:
    width, height = img.size
    longest_side = max(width, height)
    if longest_side <= max_dim:
        return img
    scale = max_dim / longest_side
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return img.resize(new_size, Image.LANCZOS)


def preprocess_image(contents: bytes) -> PreprocessedImage:
    img = Image.open(BytesIO(contents))
    img = ImageOps.exif_transpose(img)  # respect camera rotation before anything else
    img = img.convert("RGB")
    img = _resize_if_needed(img)

    # OCR-ready variant: grayscale -> autocontrast -> mild denoise -> sharpen.
    ocr_img = img.convert("L")
    ocr_img = ImageOps.autocontrast(ocr_img, cutoff=1)
    ocr_img = ocr_img.filter(ImageFilter.MedianFilter(size=3))  # denoise
    ocr_img = ocr_img.filter(ImageFilter.SHARPEN)

    width, height = img.size
    return PreprocessedImage(
        display_image=img,
        ocr_image=ocr_img,
        width=width,
        height=height,
    )


def image_to_bytes(img: Image.Image, fmt: str = "JPEG") -> bytes:
    buf = BytesIO()
    if fmt == "JPEG" and img.mode != "RGB":
        img = img.convert("RGB")
    img.save(buf, format=fmt)
    return buf.getvalue()
