import streamlit as st

from components.media import esc, h
from models.result import AnalysisResult
from services.display import (
    DISPOSAL_DISPLAY,
    DISPOSAL_ICON,
    HAZARD_DISPLAY,
    MATERIAL_CONFIDENCE_DISPLAY,
    RECOVERY_DISPLAY,
    RECOVERY_HINT,
    SAFETY_DISCLAIMER,
    get_guidance_steps,
)

_HAZARD_ICONS = {"critical": "🚨", "high": "⚠️", "medium": "⚡", "low": "✅", "unknown": "❓"}

# Reveal delays: each block enters slightly after the previous one so the
# page "builds" top-to-bottom instead of popping in all at once.
_STEP = 0.08


def _d(i: int) -> str:
    return f"--d:{i * _STEP:.2f}s"


def render_results_dashboard(result: AnalysisResult) -> None:
    st.markdown(_identification(result, 0), unsafe_allow_html=True)
    st.markdown(_safety(result, 1), unsafe_allow_html=True)
    why = _why(result, 2)
    if why:
        st.markdown(why, unsafe_allow_html=True)
    st.markdown(_materials(result, 3), unsafe_allow_html=True)
    st.markdown(_tiles(result, 6), unsafe_allow_html=True)
    st.markdown(_guidance(result, 7), unsafe_allow_html=True)
    st.markdown(h(f'<div class="disclaimer reveal" style="{_d(8)}">', esc(SAFETY_DISCLAIMER), "</div>"), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Identification — name, brand, category, animated confidence ring
# ---------------------------------------------------------------------------

def _ring(confidence: float) -> str:
    pct = round(confidence * 100)
    tone = "high" if confidence >= 0.8 else "medium" if confidence >= 0.5 else "low"
    circumference = 251.2  # 2π·40
    target = circumference * (1 - confidence)
    return h(
        f'<div class="ring {tone}" style="--target:{target:.1f}">',
        '<svg viewBox="0 0 96 96"><defs><linearGradient id="lwGradGreen" x1="0" y1="0" x2="1" y2="1">',
        '<stop offset="0" stop-color="#10b981"/><stop offset="1" stop-color="#0f766e"/></linearGradient></defs>',
        '<circle class="track" cx="48" cy="48" r="40"/><circle class="bar" cx="48" cy="48" r="40"/></svg>',
        f'<div class="ring-val pop" style="--d:.5s"><div><b>{pct}%</b><small>confidence</small></div></div>',
        "</div>",
    )


def _identification(r: AnalysisResult, i: int) -> str:
    if r.is_unknown:
        return h(
            f'<div class="card reveal" style="{_d(i)}"><div class="id-card"><div>',
            '<div class="id-eyebrow">Identification</div>',
            '<div class="id-item">Couldn&#39;t identify this item</div>',
            f'<div class="id-category">{esc(r.category)}</div>',
            '<div class="id-category" style="margin-top:.6rem">Try a photo that shows the product label, model number, or battery markings — well-lit and in focus.</div>',
            "</div>", _ring(r.confidence), "</div></div>",
        )

    source = "Vision analysis" if r.analysis_source == "vision" else "Label text analysis"
    brand = f'<div class="id-brand">{esc(r.brand_model)}</div>' if r.brand_model else ""
    return h(
        f'<div class="card reveal" style="{_d(i)}"><div class="id-card"><div>',
        '<div class="id-eyebrow">Identified as</div>',
        f'<div class="id-item">{esc(r.item)}</div>',
        brand,
        f'<div class="id-category">{esc(r.category)}</div>',
        f'<div class="id-source"><i></i>{source}</div>',
        "</div>", _ring(r.confidence), "</div></div>",
    )


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

def _safety(r: AnalysisResult, i: int) -> str:
    if r.damage_detected:
        seen = f'<div class="danger-seen"><b>What was seen:</b> {esc(r.damage_description)}</div>' if r.damage_description else ""
        return h(
            f'<div class="danger pop" style="{_d(i)}">',
            '<div class="danger-head"><span class="ic">🔋</span>Potential damaged battery / hazardous item</div>',
            seen,
            "<ul><li>⛔ Do NOT puncture, crush, or bend</li>",
            "<li>⛔ Do NOT open, disassemble, charge, or attempt repair</li>",
            "<li>🔥 Keep away from heat, flames, and flammable materials</li>",
            "<li>📞 Contact a hazardous / e-waste service immediately</li></ul></div>",
        )

    high = [m for m in r.materials if m.hazard in ("high", "critical")]
    if high:
        names = ", ".join(esc(m.name) for m in high)
        return h(
            f'<div class="alert alert-warn reveal" style="{_d(i)}"><span class="ic">⚠️</span><div>',
            f"<b>Contains high-hazard materials: {names}</b>",
            "<p>Handle with care and follow the disposal guidance below.</p></div></div>",
        )
    if r.materials:
        return h(
            f'<div class="alert alert-ok reveal" style="{_d(i)}"><span class="ic">✅</span><div>',
            "<b>No high-hazard materials identified</b><p>Still recycle it properly — see the steps below.</p></div></div>",
        )
    return h(
        f'<div class="alert alert-info reveal" style="{_d(i)}"><span class="ic">ℹ️</span><div>',
        "<b>No materials could be identified from this image</b></div></div>",
    )


# ---------------------------------------------------------------------------
# Why — explainability
# ---------------------------------------------------------------------------

def _why(r: AnalysisResult, i: int) -> str:
    ev = r.evidence
    if not r.reasoning and not ev.has_label_facts() and not ev.visible_text:
        return ""

    chips = []
    if ev.battery_chemistry:
        chips.append(("🔋", "Chemistry", ev.battery_chemistry))
    if ev.voltage:
        chips.append(("⚡", "Voltage", ev.voltage))
    if ev.capacity:
        chips.append(("🔌", "Capacity", ev.capacity))
    if ev.un_number:
        chips.append(("📦", "UN", ev.un_number))
    if ev.model_number:
        chips.append(("🏷️", "Model", ev.model_number))
    for cert in ev.certifications:
        chips.append(("✔️", "Mark", cert))

    body = []
    if r.reasoning:
        body.append(f'<p class="why-reasoning">{esc(r.reasoning)}</p>')
    if chips:
        body.append('<div class="ev-title">Found on the label</div><div class="chip-row">')
        for n, (icon, key, val) in enumerate(chips):
            body.append(f'<span class="chip pop" style="--d:{0.15 + n * 0.05:.2f}s">{icon} <span class="k">{esc(key)}</span> {esc(val)}</span>')
        body.append("</div>")
    if ev.warnings:
        body.append('<div class="ev-title">Warnings printed on the item</div>')
        body.extend(f'<div class="ev-warn"><span>⚠️</span><span>{esc(w)}</span></div>' for w in ev.warnings)
    if ev.visible_text:
        # <pre> gets mangled by Streamlit's markdown pass; a div with <br>s
        # and white-space:pre-wrap renders the label text line-by-line.
        lines = "<br>".join(esc(line) for line in ev.visible_text.splitlines())
        body.append(f'<div class="ev-title">Text read from the image</div><div class="ev-text">{lines}</div>')

    return h(
        f'<details class="why reveal" open style="{_d(i)}">',
        '<summary>🔎 Why LabelWise thinks this<span class="chev">▾</span></summary>',
        '<div class="why-body">', *body, "</div></details>",
    )


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------

def _materials(r: AnalysisResult, i: int) -> str:
    rows = [h(f'<div class="sec reveal" style="{_d(i)}"><h3>Components &amp; materials</h3>',
              f'<span class="n">{len(r.materials)} identified</span></div>')]
    if not r.materials:
        rows.append(f'<div class="alert alert-info reveal" style="{_d(i + 1)}"><span class="ic">ℹ️</span><div><b>No materials identified</b></div></div>')
        return h(*rows)

    for n, m in enumerate(r.materials):
        lvl = (m.hazard or "unknown").lower()
        conf = MATERIAL_CONFIDENCE_DISPLAY.get((m.confidence or "").lower())
        conf_html = f'<span class="conf">{esc(conf)}</span>' if conf else ""
        rows.append(h(
            f'<div class="mat in-l" style="--d:{(i + 1) * _STEP + n * 0.06:.2f}s"><span class="bar {lvl}"></span>',
            f'<span class="name">{esc(m.name)}</span>{conf_html}',
            f'<span class="hz hz-{lvl}">{_HAZARD_ICONS.get(lvl, "❓")} {HAZARD_DISPLAY.get(lvl, "UNKNOWN")}</span></div>',
        ))
    return h(*rows)


# ---------------------------------------------------------------------------
# Disposal / recovery tiles
# ---------------------------------------------------------------------------

def _tiles(r: AnalysisResult, i: int) -> str:
    d_label = DISPOSAL_DISPLAY.get(r.disposal_category, "Unknown")
    d_icon = DISPOSAL_ICON.get(r.disposal_category, "❓")
    d_tone = "tile-danger" if r.disposal_category == "hazardous_waste" else "tile-teal"

    rc_label = RECOVERY_DISPLAY.get(r.recovery_potential, "UNKNOWN")
    rc_hint = RECOVERY_HINT.get(r.recovery_potential, "")
    rc_tone = {"high": "tile-green", "moderate": "tile-amber"}.get(r.recovery_potential, "tile-neutral")

    return h(
        f'<div class="tiles">',
        f'<div class="tile {d_tone} pop" style="{_d(i)}"><span class="ic">{d_icon}</span>',
        f'<span class="eyebrow">Disposal category</span><span class="label">{esc(d_label)}</span></div>',
        f'<div class="tile {rc_tone} pop" style="{_d(i + 1)}"><span class="ic">💰</span>',
        f'<span class="eyebrow">Recovery potential</span><span class="label">{esc(rc_label)}</span>',
        f'<span class="hint">{esc(rc_hint)}</span></div>',
        "</div>",
    )


# ---------------------------------------------------------------------------
# Guidance
# ---------------------------------------------------------------------------

def _guidance(r: AnalysisResult, i: int) -> str:
    steps = get_guidance_steps(r)
    items = [
        h(f'<div class="g-step in-l" style="--d:{i * _STEP + 0.15 + n * 0.08:.2f}s">',
          f'<span class="g-n">{n + 1}</span><span class="g-t">{esc(s)}</span></div>')
        for n, s in enumerate(steps)
    ]
    return h(
        f'<div class="guide reveal" style="{_d(i)}">',
        '<div class="guide-title">🧭 What should I do now?</div>',
        *items,
        '<a class="g-link" href="https://www.google.com/maps/search/e-waste+recycling+near+me" target="_blank" rel="noopener">',
        "📍 Find recycling centers near you</a></div>",
    )
