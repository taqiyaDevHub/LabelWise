"""Small presentation helpers shared by app.py and the dashboard.

Streamlit's markdown renderer turns any line indented 4+ spaces into a code
block and any blank line into a paragraph break — so every HTML fragment we
hand it must be a single flat string. `h()` builds those safely; `thumb()`
turns an upload into a small data-URI so we can put the user's photo inside
our own styled cards (preview, scanner) instead of st.image().
"""

import base64
import html
from io import BytesIO

from PIL import Image, ImageOps


def esc(text) -> str:
    return html.escape(str(text)) if text is not None else ""


def h(*parts: str) -> str:
    """Join HTML fragments into one flat, markdown-safe string."""
    return "".join(p.strip("\r\n") for p in parts if p)


def thumb(image_bytes: bytes, max_side: int = 900) -> str:
    """Downscaled JPEG data-URI of the upload (EXIF-rotated). Keeps the
    embedded HTML small even for a 5 MB photo."""
    try:
        img = Image.open(BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((max_side, max_side))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode("ascii")
