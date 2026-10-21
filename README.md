# LabelWise

AI-powered e-waste & recycling item inspector.

Upload (or snap) a photo of an electronic item, battery, or its label. LabelWise
tells you **what it is, what's inside, how hazardous it is, why it thinks so, and
exactly what to do with it** — with safety rules that can't be overridden by the
model.

## Architecture

Two independent apps that talk over HTTP:

```
labelwise/
├── backend/    FastAPI
│   ├── routes/analyze.py          POST /analyze — HTTP wrapper
│   ├── services/pipeline.py       the pipeline as a plain function
│   ├── services/
│   │   ├── image_validator.py     size / type / decode checks
│   │   ├── preprocess.py          resize, EXIF-rotate, OCR-ready variant
│   │   ├── ocr_service.py         Tesseract + label field extraction
│   │   ├── vision_classifier.py   vision core: prompt, schema, provider
│   │   │                          selection                    (tier 1)
│   │   ├── vision_providers/
│   │   │   ├── gemini.py          Google Gemini (free tier)
│   │   │   └── claude.py          Anthropic Claude
│   │   ├── classifier.py          keyword matching on OCR text (tier 2)
│   │   ├── material_analyzer.py   category knowledge base (fallback)
│   │   ├── disposal_engine.py     rules: category → disposal, damage override
│   │   ├── recovery_engine.py     rules: category → recovery potential
│   │   └── guidance_engine.py     rules: "What should I do now?" steps
│   ├── data/*.json                the knowledge base the rules engines read
│   └── models/schemas.py          THE contract (single source of truth)
│
└── frontend/   Streamlit
    ├── app.py                     upload / camera, session state, states
    ├── components/
    │   ├── results_dashboard.py   result card, safety, "why", materials,
    │   │                          disposal/recovery, guidance (animated)
    │   ├── styling.py             CSS only — theme-aware surfaces, motion
    │   └── media.py               flat-HTML + thumbnail helpers
    ├── models/result.py           mirrors schemas.py (tolerant parser)
    └── services/
        ├── analysis_service.py    abstract interface + AnalysisError
        ├── backend_service.py     HTTP → FastAPI          (mode=backend)
        ├── local_service.py       pipeline in-process     (mode=local)
        ├── mock_service.py        canned demo results     (mode=mock)
        └── display.py             display labels + fallback guidance
```

### How classification works

```
validate → preprocess → OCR ─┬─► vision classifier (Claude)  ──┐
                             │       │ unknown / unavailable    │
                             │       ▼                          │
                             └─► keyword classifier ────────────┤
                                                                ▼
                     materials → disposal → recovery → guidance → AnalysisResult
```

- **Tier 1 — vision.** The photo goes to a vision model with a strict JSON
  schema. One call returns the item, an honest 0–1 confidence, a one-line
  *reasoning*, the materials it can see (each with high/medium/low confidence),
  any battery chemistry printed on the label, and `damage_detected` with a
  description of what was seen (swelling, leaking, corrosion, burn marks).
  Two interchangeable providers (`backend/services/vision_providers/`):
  **Gemini** (`GEMINI_API_KEY`, has a free tier) and **Claude**
  (`ANTHROPIC_API_KEY`). Same prompt, same schema — the pipeline can't tell
  them apart.
- **Tier 2 — keyword.** Deterministic whole-word matching of OCR text against
  `data/products.json`. Used when vision is off, fails, or returns *Unknown*.
- **Rules govern safety.** Whichever tier classified the item, disposal
  category, recovery potential, and guidance steps come from the JSON-driven
  rules engines. A damaged item is **always** escalated to `hazardous_waste`
  with the damage steps — enforced in code, not data.

## Run it

Requires Python 3.11+. Tesseract is optional but recommended for the OCR
evidence (Windows: [UB-Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki),
macOS: `brew install tesseract`, Debian/Ubuntu: `sudo apt-get install tesseract-ocr`).

```bash
pip install -r requirements.txt
```

Get a free Gemini key at https://aistudio.google.com (Get API key), then pick
one of the two ways to run. Everything below is from the `labelwise/` directory.

### Way 1 — single process (simplest; same setup as the cloud deploy)

The Streamlit app runs the analysis pipeline in-process. No second server.

```bash
$env:GEMINI_API_KEY = "AIza..."          # PowerShell (use export on macOS/Linux)
$env:LABELWISE_ANALYSIS_MODE = "local"
streamlit run frontend/app.py
```

Or copy `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml` and fill
it in; the app reads it automatically.

### Way 2 — API + UI as two services

**Terminal 1 — backend:**

```bash
$env:GEMINI_API_KEY = "AIza..."
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — frontend:**

```bash
streamlit run frontend/app.py
```

`GET http://localhost:8000/health` → `{"status": "ok", "vision_enabled": true, "vision_provider": "gemini"}`
tells you which mode the backend is in; the UI's status pill shows the same.

### Demo mode (no key, no backend)

```bash
$env:LABELWISE_USE_MOCK = "1"; streamlit run frontend/app.py
```

Results are keyed off the uploaded filename: contains `damage`/`swollen` →
damaged-battery escalation; `unknown`/`random` → low-confidence unknown;
`blurry`/`dark`/`poor` → poor-image error; `fail`/`error` → analysis failure;
anything else → power bank golden path.

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | — | Enables vision classification via Gemini (free tier) |
| `ANTHROPIC_API_KEY` | — | Enables vision classification via Claude |
| `LABELWISE_VISION_PROVIDER` | `auto` | `auto` (Claude if keyed, else Gemini) / `claude` / `gemini` / `off` |
| `LABELWISE_GEMINI_MODEL` | `gemini-3.6-flash` | Gemini model |
| `LABELWISE_VISION_MODEL` | `claude-opus-5` | Claude model |
| `LABELWISE_VISION_EFFORT` | `medium` | `low` / `medium` / `high` — latency vs thoroughness |
| `LABELWISE_VISION_TIMEOUT` | `45` | Seconds before falling back to keyword mode |
| `LABELWISE_VISION_ENABLED` | `1` | Set `0` to force keyword-only mode |
| `LABELWISE_CORS_ORIGINS` | `http://localhost:8501` | Comma-separated allowed origins |
| `LABELWISE_ANALYSIS_MODE` | `backend` | `backend` (HTTP to the API) / `local` (in-process, single app) / `mock` |
| `LABELWISE_BACKEND_URL` | `http://localhost:8000` | Frontend → backend (mode `backend` only) |
| `LABELWISE_USE_MOCK` | `0` | `1` = shorthand for mode `mock` |

## Deploy for free (Streamlit Community Cloud)

One app, one URL, no card. Uses `LABELWISE_ANALYSIS_MODE=local` so the whole
pipeline runs inside the Streamlit process.

1. Push this `labelwise/` folder to a GitHub repo (public or private).
2. Go to https://share.streamlit.io → sign in with GitHub → **New app**.
3. Repository: your repo · Branch: `main` · **Main file path: `frontend/app.py`**.
4. **Advanced settings** → Python version **3.11** → Secrets: paste

   ```toml
   LABELWISE_ANALYSIS_MODE = "local"
   GEMINI_API_KEY = "AIza..."
   ```

5. **Deploy**. First build takes ~3 minutes (it installs `packages.txt` →
   Tesseract, and `requirements.txt`).

The app sleeps after a few days without visitors and wakes on the next visit
(~30 s). Free-tier Gemini rate limits still apply; the UI falls back to
label-text mode if the quota is hit and shows it in the status pill.

To deploy the API separately instead (e.g. Render free tier), run
`uvicorn backend.main:app --host 0.0.0.0 --port $PORT` there and set
`LABELWISE_BACKEND_URL` on the frontend.

## Tests

```bash
pytest backend/tests -v
```

- `test_api.py` — HTTP-level: error contract, size guards, vision path, keyword
  fallback, damage escalation, generic-failure handling. OCR and vision are
  mocked, so these run anywhere.
- `test_pipeline.py` — renders label text and runs real OCR through the
  pipeline. Skipped automatically when Tesseract isn't installed.

## API contract

`POST /analyze` — `multipart/form-data`, field `file` (JPG/PNG/WEBP, ≤ 5 MB, ≤ 4096 px).

Success `200`:

```json
{
  "item": "Power Bank",
  "category": "Battery Electronics",
  "confidence": 0.94,
  "materials": [
    {"name": "Lithium-ion battery", "hazard": "high", "confidence": "high"},
    {"name": "Copper", "hazard": "low", "confidence": "medium"}
  ],
  "damage_detected": false,
  "recovery_potential": "moderate",
  "disposal_category": "battery_recycling",

  "brand_model": "Anker PowerCore 10000",
  "damage_description": null,
  "reasoning": "The label reads 'Power Bank 10000mAh' with a Li-ion marking ...",
  "evidence": {
    "battery_chemistry": "lithium-ion",
    "voltage": "3.7V",
    "capacity": "10000mAh",
    "un_number": "UN3481",
    "model_number": "A1263",
    "certifications": ["CE", "FCC", "RoHS"],
    "warnings": ["Do not disassemble"],
    "visible_text": "Anker PowerCore 10000 ...",
    "ocr_text_found": true
  },
  "guidance_steps": ["Do not place in regular household trash", "..."],
  "analysis_source": "vision"
}
```

The first seven fields are the fixed canonical contract. Everything after is
additive and optional — the frontend's `AnalysisResult.from_dict` tolerates
their absence.

Error (`422` validation/uncertainty, `500` unexpected — never a traceback):

```json
{"error": true, "message": "<exact PRD-defined user-facing string>"}
```

Enum values: `hazard` = `low | medium | high | critical | unknown`;
`materials[].confidence` = `high | medium | low`;
`disposal_category` = `general_recyclable | e_waste | battery_recycling | hazardous_waste | specialized_recycling | reuse_refurbishment | unknown`;
`recovery_potential` = `low | moderate | high | unknown`;
`analysis_source` = `vision | keyword`.

## Not built yet

- Analysis history / shareable result page
- PDF export of the result card
- Location-aware disposal guidance (rules currently generic)
- Rate limiting
- Multi-item / batch upload
