"""
Presentation-only styling for LabelWise.

UI polish only — no functionality, no data, no contract, no logic here.

Theme rule: surfaces use Streamlit's own theme variables (--background-color,
--secondary-background-color, --text-color, --primary-color) so every card,
chip and tile adapts to light/dark automatically. Color is only hard-coded
where the element also fixes its own background (hazard badges, the guidance
banner, the damage alert) — those pairs are self-contained.

Motion: every entrance is a CSS animation on mount. Streamlit re-creates
elements on rerun, so entrances replay naturally when a new result lands.
`prefers-reduced-motion` turns all of it off.
"""

import streamlit as st

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root {
    --lw-a1: #10b981;   /* emerald-500 */
    --lw-a2: #0f766e;   /* teal-700 */
    --lw-a3: #06b6d4;   /* cyan-500 — gradient sparkle only */
    --lw-radius: 16px;
    --lw-radius-sm: 10px;
    --lw-ease: cubic-bezier(.22,.61,.36,1);
    --lw-spring: cubic-bezier(.34,1.56,.64,1);
    --lw-surface: color-mix(in srgb, var(--secondary-background-color, #f4f6f8) 85%, var(--background-color, #fff));
    --lw-border: color-mix(in srgb, var(--text-color, #111) 12%, transparent);
    --lw-muted: color-mix(in srgb, var(--text-color, #111) 62%, transparent);
    --lw-faint: color-mix(in srgb, var(--text-color, #111) 40%, transparent);
    --lw-shadow: 0 1px 2px rgba(0,0,0,.05), 0 8px 24px -12px rgba(0,0,0,.18);
    --lw-shadow-hover: 0 2px 4px rgba(0,0,0,.06), 0 18px 40px -16px rgba(0,0,0,.28);
}

html, body, .stApp { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

/* Ambient background — two soft accent blobs that drift very slowly.
   .stApp is made a stacking context so z-index:-1 puts them above its
   background but below every piece of content. */
.stApp { isolation: isolate; }
.stApp::before, .stApp::after {
    content: ""; position: fixed; z-index: -1; pointer-events: none;
    width: 60vw; height: 60vw; border-radius: 50%; filter: blur(80px); opacity: .18;
}
.stApp::before { top: -25vw; right: -20vw; background: var(--lw-a1); animation: lw-drift 26s ease-in-out infinite alternate; }
.stApp::after  { bottom: -30vw; left: -25vw; background: var(--lw-a3); animation: lw-drift 32s ease-in-out infinite alternate-reverse; }
@keyframes lw-drift { from { transform: translate(0,0) scale(1); } to { transform: translate(6vw,4vw) scale(1.12); } }
.block-container { padding-top: 4.25rem; max-width: 52rem; }

/* ---------- Motion primitives ---------- */
@keyframes lw-up   { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
@keyframes lw-pop  { from { opacity: 0; transform: scale(.85); } 70% { transform: scale(1.04); } to { opacity: 1; transform: none; } }
@keyframes lw-in-l { from { opacity: 0; transform: translateX(-12px); } to { opacity: 1; transform: none; } }
@keyframes lw-grow { from { width: 0; } }
@keyframes lw-ring { to { stroke-dashoffset: var(--target); } }
@keyframes lw-shimmer { from { transform: translateX(-120%) skewX(-18deg); } to { transform: translateX(220%) skewX(-18deg); } }
@keyframes lw-pulse-red { 0%,100% { box-shadow: 0 0 0 0 rgba(239,68,68,.45); } 60% { box-shadow: 0 0 0 14px rgba(239,68,68,0); } }
@keyframes lw-float { 0%,100% { transform: translateY(0) rotate(-3deg); } 50% { transform: translateY(-6px) rotate(3deg); } }
@keyframes lw-hue  { from { background-position: 0% 50%; } to { background-position: 100% 50%; } }
@keyframes lw-scan { 0% { top: 0; opacity: 0; } 8% { opacity: 1; } 92% { opacity: 1; } 100% { top: 100%; opacity: 0; } }
@keyframes lw-dots { 0% { content: ""; } 33% { content: "."; } 66% { content: ".."; } 100% { content: "..."; } }
@keyframes lw-cycle { 0%, 18% { opacity: 1; transform: none; } 25%, 100% { opacity: 0; transform: translateY(-6px); } }
@keyframes lw-spin { to { transform: rotate(360deg); } }
@keyframes lw-border-breathe { 0%,100% { border-color: color-mix(in srgb, var(--lw-a2) 55%, transparent); } 50% { border-color: color-mix(in srgb, var(--lw-a1) 100%, transparent); } }

.reveal { animation: lw-up .55s var(--lw-ease) both; animation-delay: var(--d, 0s); }
.pop    { animation: lw-pop .5s var(--lw-spring) both; animation-delay: var(--d, 0s); }
.in-l   { animation: lw-in-l .45s var(--lw-ease) both; animation-delay: var(--d, 0s); }

/* ---------- Hero ---------- */
.hero { padding: .25rem 0 1.25rem 0; }
.hero-row { display: flex; align-items: center; gap: .8rem; }
.hero-badge {
    width: 3.1rem; height: 3.1rem; border-radius: 14px; display: grid; place-items: center; font-size: 1.6rem;
    background: linear-gradient(135deg, var(--lw-a1), var(--lw-a2)); box-shadow: 0 10px 24px -10px rgba(15,118,110,.7);
    animation: lw-float 5s ease-in-out infinite;
}
.hero-title {
    font-size: 2.4rem; font-weight: 900; letter-spacing: -.035em; line-height: 1.05;
    background: linear-gradient(90deg, var(--lw-a2), var(--lw-a1), var(--lw-a3), var(--lw-a2));
    background-size: 300% 100%; -webkit-background-clip: text; background-clip: text; color: transparent;
    animation: lw-hue 9s linear infinite;
}
.hero-tagline { font-size: 1.05rem; font-weight: 600; color: var(--lw-muted); margin-top: .1rem; }
.hero-sub { font-size: .95rem; color: var(--lw-muted); margin-top: .75rem; max-width: 40rem; line-height: 1.55; }

.steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: .6rem; margin: 1rem 0 .5rem 0; }
.step {
    padding: .8rem .9rem; border-radius: var(--lw-radius-sm); background: var(--lw-surface); border: 1px solid var(--lw-border);
    display: flex; gap: .6rem; align-items: flex-start; transition: transform .25s var(--lw-ease), box-shadow .25s var(--lw-ease);
}
.step:hover { transform: translateY(-2px); box-shadow: var(--lw-shadow); }
.step-n {
    flex: none; width: 1.6rem; height: 1.6rem; border-radius: 50%; display: grid; place-items: center; font-size: .8rem; font-weight: 800;
    color: #fff; background: linear-gradient(135deg, var(--lw-a1), var(--lw-a2));
}
.step-t { font-weight: 700; font-size: .9rem; line-height: 1.2; }
.step-s { font-size: .78rem; color: var(--lw-muted); margin-top: .15rem; line-height: 1.3; }

/* Status pills under the hero */
.pill {
    display: inline-flex; align-items: center; gap: .45rem; padding: .35rem .75rem; border-radius: 999px; font-size: .8rem; font-weight: 600;
    background: var(--lw-surface); border: 1px solid var(--lw-border); color: var(--lw-muted);
}
.pill .dot { width: .5rem; height: .5rem; border-radius: 50%; background: #9ca3af; }
.pill.ok .dot { background: var(--lw-a1); box-shadow: 0 0 0 3px color-mix(in srgb, var(--lw-a1) 25%, transparent); }
.pill.warn .dot { background: #f59e0b; box-shadow: 0 0 0 3px rgba(245,158,11,.25); }
.pill.off .dot { background: #ef4444; box-shadow: 0 0 0 3px rgba(239,68,68,.22); }

/* ---------- Input area ---------- */
div[data-testid="stRadio"] > div { gap: .35rem; }
div[data-testid="stRadio"] label {
    padding: .45rem .9rem; border-radius: 999px; border: 1px solid var(--lw-border); background: var(--lw-surface);
    transition: background .2s, border-color .2s, transform .2s var(--lw-ease);
}
div[data-testid="stRadio"] label:hover { transform: translateY(-1px); border-color: var(--lw-a2); }

[data-testid="stFileUploaderDropzone"] {
    border: 2px dashed color-mix(in srgb, var(--lw-a2) 55%, transparent);
    border-radius: var(--lw-radius);
    background: color-mix(in srgb, var(--lw-a1) 6%, var(--lw-surface));
    transition: transform .25s var(--lw-ease), box-shadow .25s var(--lw-ease), background .25s;
    animation: lw-border-breathe 3.2s ease-in-out infinite;
}
[data-testid="stFileUploaderDropzone"]:hover {
    transform: translateY(-2px); box-shadow: var(--lw-shadow-hover);
    background: color-mix(in srgb, var(--lw-a1) 11%, var(--lw-surface));
}

/* Preview card */
.preview {
    border-radius: var(--lw-radius); overflow: hidden; border: 1px solid var(--lw-border); background: var(--lw-surface);
    box-shadow: var(--lw-shadow); position: relative;
}
.preview img { display: block; width: 100%; max-height: 380px; object-fit: contain; background: #0b0f14; transition: transform .6s var(--lw-ease); }
.preview:hover img { transform: scale(1.03); }
.preview-meta { display: flex; justify-content: space-between; align-items: center; padding: .6rem .85rem; font-size: .8rem; color: var(--lw-muted); }
.preview-meta b { color: var(--text-color, inherit); font-weight: 600; }

/* Primary button: gradient + shimmer sweep */
.stButton > button[kind="primary"] {
    position: relative; overflow: hidden;
    background: linear-gradient(135deg, var(--lw-a1) 0%, var(--lw-a2) 100%);
    color: #fff !important; font-weight: 800; letter-spacing: .01em; border: none; border-radius: var(--lw-radius-sm);
    padding: .7rem 1.5rem; box-shadow: 0 10px 22px -10px rgba(15,118,110,.7);
    transition: transform .18s var(--lw-spring), box-shadow .25s var(--lw-ease);
}
.stButton > button[kind="primary"] p { color: #fff !important; }
.stButton > button[kind="primary"]::after {
    content: ""; position: absolute; inset: 0; width: 40%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,.35), transparent);
    transform: translateX(-120%) skewX(-18deg);
}
.stButton > button[kind="primary"]:hover { transform: translateY(-2px) scale(1.01); box-shadow: 0 16px 30px -12px rgba(15,118,110,.85); }
.stButton > button[kind="primary"]:hover::after { animation: lw-shimmer .9s var(--lw-ease); }
.stButton > button[kind="primary"]:active { transform: translateY(0) scale(.98); }
.stButton > button {
    border-radius: var(--lw-radius-sm); font-weight: 600; transition: transform .18s var(--lw-spring), box-shadow .25s, border-color .2s;
}
.stButton > button:not([kind="primary"]):hover { transform: translateY(-1px); border-color: var(--lw-a2); box-shadow: var(--lw-shadow); }

/* ---------- Scanner (shown while the backend works) ---------- */
.scan-wrap {
    border-radius: var(--lw-radius); overflow: hidden; border: 1px solid var(--lw-border); background: #0b0f14; position: relative;
    box-shadow: var(--lw-shadow-hover);
}
.scan-wrap img { display: block; width: 100%; max-height: 380px; object-fit: contain; filter: saturate(.9) brightness(.85); }
.scan-line {
    position: absolute; left: 0; right: 0; height: 3px; top: 0;
    background: linear-gradient(90deg, transparent, var(--lw-a1), #fff, var(--lw-a1), transparent);
    box-shadow: 0 0 18px 4px color-mix(in srgb, var(--lw-a1) 60%, transparent);
    animation: lw-scan 2.1s ease-in-out infinite;
}
.scan-grid {
    position: absolute; inset: 0; pointer-events: none; opacity: .28;
    background-image: linear-gradient(color-mix(in srgb, var(--lw-a1) 35%, transparent) 1px, transparent 1px),
                      linear-gradient(90deg, color-mix(in srgb, var(--lw-a1) 35%, transparent) 1px, transparent 1px);
    background-size: 28px 28px;
}
.scan-corner { position: absolute; width: 26px; height: 26px; border: 3px solid var(--lw-a1); }
.scan-corner.tl { top: 10px; left: 10px; border-right: 0; border-bottom: 0; border-radius: 6px 0 0 0; }
.scan-corner.tr { top: 10px; right: 10px; border-left: 0; border-bottom: 0; border-radius: 0 6px 0 0; }
.scan-corner.bl { bottom: 10px; left: 10px; border-right: 0; border-top: 0; border-radius: 0 0 0 6px; }
.scan-corner.br { bottom: 10px; right: 10px; border-left: 0; border-top: 0; border-radius: 0 0 6px 0; }
.scan-status { display: flex; align-items: center; gap: .7rem; margin-top: .9rem; }
.scan-spinner {
    width: 1.15rem; height: 1.15rem; border-radius: 50%; border: 2.5px solid var(--lw-border); border-top-color: var(--lw-a1);
    animation: lw-spin .8s linear infinite; flex: none;
}
.scan-title { font-weight: 700; }
.scan-title::after { content: ""; display: inline-block; width: 1.2em; text-align: left; animation: lw-dots 1.2s steps(1) infinite; }
.scan-cycle { position: relative; height: 1.3rem; font-size: .85rem; color: var(--lw-muted); overflow: hidden; }
.scan-cycle span { position: absolute; left: 0; opacity: 0; animation: lw-cycle 8s ease-in-out infinite; }
.scan-cycle span:nth-child(1) { animation-delay: 0s; }
.scan-cycle span:nth-child(2) { animation-delay: 2s; }
.scan-cycle span:nth-child(3) { animation-delay: 4s; }
.scan-cycle span:nth-child(4) { animation-delay: 6s; }

/* ---------- Result: identification card ---------- */
.card {
    border-radius: var(--lw-radius); background: var(--lw-surface); border: 1px solid var(--lw-border);
    box-shadow: var(--lw-shadow); padding: 1.15rem 1.3rem;
    transition: transform .25s var(--lw-ease), box-shadow .25s var(--lw-ease);
}
.card:hover { box-shadow: var(--lw-shadow-hover); }
.id-card { display: grid; grid-template-columns: 1fr auto; gap: 1rem; align-items: center; }
.id-eyebrow { font-size: .72rem; font-weight: 800; text-transform: uppercase; letter-spacing: .1em; color: var(--lw-a2); }
.id-item { font-size: 1.9rem; font-weight: 900; letter-spacing: -.025em; line-height: 1.1; margin-top: .2rem; }
.id-brand { font-size: .95rem; font-weight: 600; margin-top: .25rem; }
.id-category { font-size: .88rem; color: var(--lw-muted); margin-top: .2rem; }
.id-source { display: inline-flex; align-items: center; gap: .35rem; margin-top: .6rem; font-size: .75rem; font-weight: 600; color: var(--lw-muted); }
.id-source i { width: .45rem; height: .45rem; border-radius: 50%; background: var(--lw-a1); display: inline-block; }

.ring { position: relative; width: 96px; height: 96px; }
.ring svg { transform: rotate(-90deg); width: 96px; height: 96px; }
.ring circle { fill: none; stroke-width: 8; stroke-linecap: round; }
.ring .track { stroke: var(--lw-border); }
.ring .bar { stroke-dasharray: 251.2; stroke-dashoffset: 251.2; animation: lw-ring 1.3s var(--lw-ease) .25s forwards; }
.ring.high .bar { stroke: url(#lwGradGreen); }
.ring.medium .bar { stroke: #f59e0b; }
.ring.low .bar { stroke: #9ca3af; }
.ring-val { position: absolute; inset: 0; display: grid; place-items: center; text-align: center; line-height: 1; }
.ring-val b { font-size: 1.35rem; font-weight: 900; letter-spacing: -.02em; display: block; }
.ring-val small { font-size: .62rem; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--lw-muted); }

/* ---------- Alerts ---------- */
.alert { border-radius: var(--lw-radius); padding: 1rem 1.15rem; border: 1px solid; display: flex; gap: .85rem; align-items: flex-start; }
.alert .ic { font-size: 1.4rem; line-height: 1; flex: none; margin-top: .1rem; }
.alert b { display: block; font-size: .95rem; margin-bottom: .2rem; }
.alert p { margin: 0; font-size: .9rem; line-height: 1.5; }
.alert-ok   { background: color-mix(in srgb, #10b981 12%, var(--lw-surface)); border-color: color-mix(in srgb, #10b981 40%, transparent); }
.alert-warn { background: color-mix(in srgb, #f59e0b 13%, var(--lw-surface)); border-color: color-mix(in srgb, #f59e0b 45%, transparent); }
.alert-info { background: color-mix(in srgb, #3b82f6 10%, var(--lw-surface)); border-color: color-mix(in srgb, #3b82f6 35%, transparent); }

.danger {
    border-radius: var(--lw-radius); padding: 1.15rem 1.3rem; color: #fff;
    background: linear-gradient(135deg, #b91c1c, #7f1d1d); border: 2px solid #ef4444;
    animation: lw-pulse-red 2s ease-out infinite;
}
.danger-head { display: flex; align-items: center; gap: .6rem; font-weight: 900; font-size: 1.05rem; letter-spacing: .01em; }
.danger-head .ic { font-size: 1.5rem; }
.danger-seen { margin: .6rem 0; padding: .6rem .8rem; border-radius: 10px; background: rgba(255,255,255,.12); font-size: .9rem; line-height: 1.45; }
.danger ul { margin: .5rem 0 0 0; padding-left: 1.2rem; }
.danger li { margin: .25rem 0; font-weight: 600; font-size: .92rem; }

/* ---------- Why / evidence ---------- */
details.why { border-radius: var(--lw-radius); background: var(--lw-surface); border: 1px solid var(--lw-border); box-shadow: var(--lw-shadow); overflow: hidden; }
details.why summary {
    list-style: none; cursor: pointer; padding: .9rem 1.2rem; font-weight: 700; display: flex; align-items: center; gap: .6rem;
    transition: background .2s;
}
details.why summary::-webkit-details-marker { display: none; }
details.why summary:hover { background: color-mix(in srgb, var(--lw-a1) 8%, transparent); }
details.why summary .chev { margin-left: auto; transition: transform .3s var(--lw-ease); color: var(--lw-muted); }
details.why[open] summary .chev { transform: rotate(180deg); }
.why-body { padding: 0 1.2rem 1.1rem 1.2rem; animation: lw-up .4s var(--lw-ease) both; }
.why-reasoning {
    font-size: .98rem; line-height: 1.55; margin: 0 0 .8rem 0; padding-left: .9rem;
    border-left: 3px solid var(--lw-a1);
}
.ev-title { font-size: .7rem; font-weight: 800; text-transform: uppercase; letter-spacing: .1em; color: var(--lw-faint); margin: .8rem 0 .4rem 0; }
.chip-row { display: flex; flex-wrap: wrap; gap: .45rem; }
.chip {
    display: inline-flex; align-items: center; gap: .35rem; padding: .3rem .7rem; border-radius: 999px; font-size: .84rem; font-weight: 700;
    background: color-mix(in srgb, var(--lw-a1) 13%, var(--lw-surface)); border: 1px solid color-mix(in srgb, var(--lw-a2) 35%, transparent);
    transition: transform .2s var(--lw-spring), box-shadow .2s;
}
.chip:hover { transform: translateY(-2px) scale(1.03); box-shadow: var(--lw-shadow); }
.chip .k { font-weight: 500; color: var(--lw-muted); }
.ev-warn { margin: .25rem 0; font-size: .9rem; display: flex; gap: .5rem; }
.ev-text {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .82rem; line-height: 1.5; white-space: pre-wrap;
    background: color-mix(in srgb, var(--text-color, #111) 5%, transparent); border: 1px solid var(--lw-border);
    padding: .7rem .85rem; border-radius: 10px; margin: 0;
}

/* ---------- Section headings ---------- */
.sec { display: flex; align-items: baseline; gap: .6rem; margin: 1.4rem 0 .6rem 0; }
.sec h3 { margin: 0 !important; font-size: 1.05rem !important; font-weight: 800 !important; letter-spacing: -.01em; }
.sec .n { font-size: .75rem; font-weight: 700; color: var(--lw-muted); }

/* ---------- Materials ---------- */
.mat {
    display: flex; align-items: center; gap: .7rem; padding: .7rem .9rem; margin: .4rem 0; border-radius: 12px;
    background: var(--lw-surface); border: 1px solid var(--lw-border);
    transition: transform .2s var(--lw-ease), box-shadow .2s var(--lw-ease), border-color .2s;
}
.mat:hover { transform: translateX(4px); box-shadow: var(--lw-shadow); border-color: color-mix(in srgb, var(--lw-a2) 40%, transparent); }
.mat .bar { width: 4px; align-self: stretch; border-radius: 4px; flex: none; }
.mat .name { font-weight: 700; flex: 1; }
.mat .conf { font-size: .74rem; color: var(--lw-muted); white-space: nowrap; }
.mat .bar.high, .mat .bar.critical { background: #ef4444; }
.mat .bar.medium { background: #f59e0b; }
.mat .bar.low { background: #10b981; }
.mat .bar.unknown { background: #9ca3af; }

.hz { padding: .22rem .65rem; border-radius: 7px; font-weight: 800; font-size: .74rem; letter-spacing: .04em; white-space: nowrap; }
.hz-high     { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }
.hz-medium   { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
.hz-low      { background: #d1fae5; color: #065f46; border: 1px solid #6ee7b7; }
.hz-critical { background: #fecaca; color: #7f1d1d; border: 2px solid #ef4444; }
.hz-unknown  { background: #f3f4f6; color: #4b5563; border: 1px solid #d1d5db; }

/* ---------- Tiles ---------- */
.tiles { display: grid; grid-template-columns: 1fr 1fr; gap: .8rem; }
.tile {
    border-radius: var(--lw-radius); padding: 1.1rem 1rem; text-align: center; position: relative; overflow: hidden;
    display: flex; flex-direction: column; align-items: center; gap: .2rem; min-height: 7.2rem;
    transition: transform .25s var(--lw-ease), box-shadow .25s var(--lw-ease);
}
.tile::before {
    content: ""; position: absolute; inset: -40% -40% auto auto; width: 70%; height: 140%; opacity: .18; border-radius: 50%;
    background: radial-gradient(circle, #fff, transparent 60%);
}
.tile:hover { transform: translateY(-3px); box-shadow: var(--lw-shadow-hover); }
.tile .ic { font-size: 1.7rem; line-height: 1; }
.tile .eyebrow { font-size: .68rem; font-weight: 800; text-transform: uppercase; letter-spacing: .1em; opacity: .8; }
.tile .label { font-size: 1.15rem; font-weight: 900; letter-spacing: -.01em; }
.tile .hint { font-size: .76rem; opacity: .85; margin-top: .1rem; }
.tile-teal    { background: linear-gradient(135deg, #ccfbf1, #99f6e4); color: #115e59; }
.tile-danger  { background: linear-gradient(135deg, #fee2e2, #fecaca); color: #991b1b; border: 2px solid #ef4444; }
.tile-green   { background: linear-gradient(135deg, #d1fae5, #a7f3d0); color: #065f46; }
.tile-amber   { background: linear-gradient(135deg, #fef3c7, #fde68a); color: #92400e; }
.tile-neutral { background: linear-gradient(135deg, #f3f4f6, #e5e7eb); color: #374151; }

/* ---------- Guidance ---------- */
.guide {
    position: relative; overflow: hidden; border-radius: var(--lw-radius); color: #fff; padding: 1.35rem 1.5rem; margin-top: 1.2rem;
    background: linear-gradient(135deg, var(--lw-a1) 0%, var(--lw-a2) 100%); box-shadow: 0 20px 40px -18px rgba(15,118,110,.8);
}
.guide::after {
    content: ""; position: absolute; inset: 0; pointer-events: none; opacity: .35;
    background: radial-gradient(circle at 90% 10%, rgba(255,255,255,.35), transparent 40%);
}
.guide-title { font-size: 1.2rem; font-weight: 900; letter-spacing: -.01em; margin-bottom: .8rem; display: flex; gap: .5rem; align-items: center; }
.g-step { display: flex; gap: .75rem; align-items: flex-start; padding: .38rem 0; }
.g-n {
    flex: none; width: 1.55rem; height: 1.55rem; border-radius: 50%; display: grid; place-items: center; font-size: .78rem; font-weight: 900;
    background: rgba(255,255,255,.22); border: 1px solid rgba(255,255,255,.45);
}
.g-t { font-size: .97rem; font-weight: 500; line-height: 1.45; padding-top: .1rem; }
.g-link {
    display: inline-flex; align-items: center; gap: .45rem; margin-top: 1rem; padding: .55rem 1rem; border-radius: 999px;
    background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.4); color: #fff !important; font-weight: 700; text-decoration: none !important;
    transition: background .2s, transform .2s var(--lw-spring);
}
.g-link:hover { background: rgba(255,255,255,.3); transform: translateY(-1px); }

.disclaimer { font-size: .78rem; color: var(--lw-faint); line-height: 1.5; margin-top: 1.1rem; padding-top: .8rem; border-top: 1px solid var(--lw-border); }

/* ---------- Error card ---------- */
.err {
    border-radius: var(--lw-radius); padding: 1.2rem 1.3rem; display: flex; gap: .9rem; align-items: flex-start;
    background: color-mix(in srgb, #ef4444 10%, var(--lw-surface)); border: 1px solid color-mix(in srgb, #ef4444 45%, transparent);
}
.err .ic { font-size: 1.6rem; line-height: 1; }
.err b { display: block; font-size: 1rem; margin-bottom: .2rem; }
.err p { margin: 0; font-size: .92rem; line-height: 1.5; color: var(--lw-muted); }

/* ---------- Misc ---------- */
.stAlert { border-radius: var(--lw-radius); }
[data-testid="stImage"] img { border-radius: var(--lw-radius); }
a { color: var(--lw-a2); text-decoration: none; font-weight: 500; }
a:hover { text-decoration: underline; }

@media (max-width: 720px) {
    .hero-title { font-size: 1.85rem; }
    .id-item { font-size: 1.45rem; }
    .steps { grid-template-columns: 1fr; }
    .tiles { grid-template-columns: 1fr; }
    .id-card { grid-template-columns: 1fr; }
    .ring { margin-top: .4rem; }
}

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation: none !important; transition: none !important; }
    .ring .bar { stroke-dashoffset: var(--target) !important; }
}
</style>
"""


def apply_custom_styles() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
