import os

import streamlit as st

from components.media import esc, h, thumb
from components.results_dashboard import render_results_dashboard
from components.styling import apply_custom_styles
from services.analysis_service import AnalysisError
from services.backend_service import BackendAnalysisService
from services.local_service import LocalAnalysisService
from services.mock_service import MockAnalysisService

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_TYPES = ["jpg", "jpeg", "png", "webp"]

ERR_TOO_LARGE = "This image exceeds the 5 MB upload limit."
ERR_ANALYSIS_FAILURE = "LabelWise couldn't complete the analysis. Please try again."

st.set_page_config(page_title="LabelWise", page_icon="♻️", layout="centered")
apply_custom_styles()


def _export_secrets_to_env() -> None:
    # On Streamlit Community Cloud, configuration lives in st.secrets. The
    # backend code reads plain environment variables (GEMINI_API_KEY, ...),
    # so mirror top-level string secrets into os.environ once per process.
    # Local dev without a secrets file is the normal case — ignore quietly.
    try:
        for key, value in st.secrets.items():
            if isinstance(value, str) and key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass


_export_secrets_to_env()

# How the UI gets its analysis (LABELWISE_ANALYSIS_MODE):
#   backend (default) HTTP to the FastAPI server at LABELWISE_BACKEND_URL
#   local             run the backend pipeline in-process — single-app
#                     deploys (Streamlit Community Cloud), no server needed
#   mock              canned results keyed off the filename, for UI demos
# LABELWISE_USE_MOCK=1 is kept as a shorthand for mode=mock.
MODE = os.environ.get("LABELWISE_ANALYSIS_MODE", "backend").strip().lower()
if os.environ.get("LABELWISE_USE_MOCK") == "1":
    MODE = "mock"
USE_MOCK = MODE == "mock"
if MODE == "mock":
    service = MockAnalysisService()
elif MODE == "local":
    service = LocalAnalysisService()
else:
    service = BackendAnalysisService()


# ---------------------------------------------------------------------------
# Session state — results survive reruns (any widget interaction reruns the
# script; without this the dashboard vanished the moment you touched anything).
# ---------------------------------------------------------------------------

for _key in ("result", "error", "image_bytes", "image_name", "thumb"):
    st.session_state.setdefault(_key, None)


def _reset() -> None:
    for key in ("result", "error", "image_bytes", "image_name", "thumb"):
        st.session_state[key] = None


def _scanner_html(data_uri: str) -> str:
    # Shown while the request is in flight. The cycling captions describe
    # what the pipeline genuinely does; they're a loop, not fake progress.
    return h(
        '<div class="scan-wrap pop">',
        f'<img src="{data_uri}" alt="">',
        '<div class="scan-grid"></div><div class="scan-line"></div>',
        '<span class="scan-corner tl"></span><span class="scan-corner tr"></span>',
        '<span class="scan-corner bl"></span><span class="scan-corner br"></span>',
        "</div>",
        '<div class="scan-status"><span class="scan-spinner"></span><div>',
        '<div class="scan-title">Analyzing</div>',
        '<div class="scan-cycle"><span>Reading the label</span><span>Identifying the item</span>',
        '<span>Checking for visible damage</span><span>Matching disposal &amp; safety rules</span></div>',
        "</div></div>",
    )


def _run_analysis(image_bytes: bytes, filename: str, slot) -> None:
    st.session_state["result"] = None
    st.session_state["error"] = None
    slot.markdown(_scanner_html(st.session_state["thumb"]), unsafe_allow_html=True)
    try:
        st.session_state["result"] = service.analyze_image(image_bytes, filename)
    except AnalysisError as e:
        st.session_state["error"] = e.message
    except Exception:
        st.session_state["error"] = ERR_ANALYSIS_FAILURE
    finally:
        slot.empty()


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    h(
        '<div class="hero reveal"><div class="hero-row"><div class="hero-badge">♻️</div>',
        '<div class="hero-title">LabelWise</div></div>',
        '<div class="hero-tagline">Know what it contains. Know what to do with it.</div>',
        '<div class="hero-sub">Snap a photo of an electronic item, battery, or its label. LabelWise identifies what it is, ',
        "what&#39;s inside, how hazardous it is, and exactly how to dispose of it safely.</div></div>",
    ),
    unsafe_allow_html=True,
)

if USE_MOCK:
    status_pill = '<span class="pill warn"><span class="dot"></span>Demo mode — simulated results</span>'
else:
    @st.cache_data(ttl=30, show_spinner=False)
    def _backend_health():
        return service.health()

    status = _backend_health()
    if status is None:
        status_pill = '<span class="pill off"><span class="dot"></span>Backend not reachable — start it with <code>uvicorn backend.main:app --port 8000</code>, or set <code>LABELWISE_ANALYSIS_MODE=local</code></span>'
    elif status.get("vision_enabled"):
        provider = {"claude": "Claude", "gemini": "Gemini"}.get(status.get("vision_provider"), "")
        status_pill = f'<span class="pill ok"><span class="dot"></span>Vision analysis active{" · " + provider if provider else ""}</span>'
    else:
        status_pill = '<span class="pill warn"><span class="dot"></span>Label-text mode — set <code>GEMINI_API_KEY</code> (free) or <code>ANTHROPIC_API_KEY</code> for full vision analysis</span>'

st.markdown(h('<div class="reveal" style="--d:.1s">', status_pill, "</div>"), unsafe_allow_html=True)

idle = st.session_state["result"] is None and st.session_state["error"] is None

# ---------------------------------------------------------------------------
# Input — upload or camera
# ---------------------------------------------------------------------------

if idle:
    st.markdown(
        h(
            '<div class="steps">',
            '<div class="step reveal" style="--d:.15s"><span class="step-n">1</span><div><div class="step-t">📷 Upload</div><div class="step-s">A clear photo of the item or its label</div></div></div>',
            '<div class="step reveal" style="--d:.22s"><span class="step-n">2</span><div><div class="step-t">🔍 Analyze</div><div class="step-s">Materials, hazards, and visible damage</div></div></div>',
            '<div class="step reveal" style="--d:.29s"><span class="step-n">3</span><div><div class="step-t">♻️ Dispose safely</div><div class="step-s">Clear next steps and where to take it</div></div></div>',
            "</div>",
        ),
        unsafe_allow_html=True,
    )

    # Only the chosen input is rendered: st.camera_input asks the browser for
    # camera permission as soon as it exists on the page, even inside a hidden
    # tab, so we don't mount it until the user actually picks "Camera".
    mode = st.radio(
        "How do you want to add the photo?",
        ["📁 Upload a photo", "📷 Use camera"],
        horizontal=True,
        label_visibility="collapsed",
    )

    image_bytes = None
    image_name = None

    if mode.startswith("📁"):
        uploaded = st.file_uploader(
            "Upload an image",
            type=ALLOWED_TYPES,
            label_visibility="collapsed",
            help="JPG, PNG, or WEBP — max 5 MB. The backend performs full validation.",
        )
        if uploaded is not None:
            if uploaded.size > MAX_FILE_SIZE:
                st.error(ERR_TOO_LARGE)
            else:
                # getvalue() (not read()) — a preview may have advanced the
                # buffer cursor, which would make a later .read() return b"".
                image_bytes = uploaded.getvalue()
                image_name = uploaded.name
    else:
        shot = st.camera_input("Take a photo of the item or its label", label_visibility="collapsed")
        if shot is not None:
            image_bytes = shot.getvalue()
            image_name = "camera.jpg"

    if image_bytes is not None:
        data_uri = thumb(image_bytes)
        st.markdown(
            h(
                '<div class="preview pop">',
                f'<img src="{data_uri}" alt="Selected photo">',
                f'<div class="preview-meta"><span><b>{esc(image_name)}</b></span><span>{len(image_bytes) / 1024:.0f} KB · ready</span></div>',
                "</div>",
            ),
            unsafe_allow_html=True,
        )
        slot = st.empty()
        if st.button("🔍 Analyze this item", type="primary", use_container_width=True):
            st.session_state["image_bytes"] = image_bytes
            st.session_state["image_name"] = image_name
            st.session_state["thumb"] = data_uri
            _run_analysis(image_bytes, image_name, slot)
            st.rerun()

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

elif st.session_state["error"] is not None:
    st.markdown(
        h(
            '<div class="err pop"><span class="ic">😕</span><div>',
            f'<b>{esc(st.session_state["error"])}</b>',
            "<p>Tip: a sharp, well-lit photo of the product label or battery markings gives the best result.</p></div></div>",
        ),
        unsafe_allow_html=True,
    )
    if st.session_state["thumb"]:
        st.markdown(
            h('<div class="preview reveal" style="--d:.1s;max-width:320px">', f'<img src="{st.session_state["thumb"]}" alt="">', "</div>"),
            unsafe_allow_html=True,
        )
    slot = st.empty()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 Try again", type="primary", use_container_width=True) and st.session_state["image_bytes"]:
            _run_analysis(st.session_state["image_bytes"], st.session_state["image_name"], slot)
            st.rerun()
    with c2:
        if st.button("📷 Use a different photo", use_container_width=True):
            _reset()
            st.rerun()

else:
    top_left, top_right = st.columns([3, 2], vertical_alignment="center")
    with top_left:
        if st.session_state["thumb"]:
            st.markdown(
                h('<div class="preview reveal" style="max-width:300px">', f'<img src="{st.session_state["thumb"]}" alt="" style="max-height:200px">', "</div>"),
                unsafe_allow_html=True,
            )
    with top_right:
        if st.button("📷 Analyze another item", use_container_width=True):
            _reset()
            st.rerun()

    render_results_dashboard(st.session_state["result"])
