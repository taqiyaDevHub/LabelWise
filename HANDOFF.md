# LabelWise Backend — HANDOFF

## Status: vision classification live, rules engines unchanged
`/analyze` runs:

```
validate -> preprocess -> OCR -> vision classify (Claude) -> [keyword fallback]
         -> materials -> disposal -> recovery -> guidance -> AnalysisResult
```

Changed in this round (see README.md for the full picture):
- `services/vision_classifier.py` + `services/vision_providers/{claude,gemini}.py`
  — NEW. A vision model looks at the actual photo and
  returns item / confidence / reasoning / materials with per-material
  confidence / battery chemistry (only if printed) / `damage_detected` with a
  description. Structured output via `client.messages.parse()` against a
  Pydantic schema, so a malformed response can't reach the route. Any API
  failure or refusal returns `None` and the route falls back to the keyword
  classifier — the demo never hard-depends on the network.
- `damage_detected` is now REAL (from vision). The disposal-engine override
  and the new `guidance_engine` damage steps are wired to it.
- `services/guidance_engine.py` + `data/guidance.json` — NEW. "What should I
  do now?" moved out of the frontend; backend is the source of truth.
- `models/schemas.py` — additive fields only: `brand_model`,
  `damage_description`, `reasoning`, `evidence{...}`, `guidance_steps`,
  `analysis_source`, and `Material.confidence`. The original 7 fields are
  untouched. `HealthResponse.vision_enabled` added.
- `classifier.py` — keyword matching is whole-word now (was substring:
  "pcb" matched inside "upcbx" etc.).
- `ocr_service.py` — CE mark matched as uppercase `CE` on the original text
  (lowercase "ce" was a constant false positive).
- `main.py` — Content-Length guard rejects oversized uploads before the body
  is parsed; route reads with a hard cap as second line of defense. CORS
  origin is configurable (`LABELWISE_CORS_ORIGINS`), no longer `*`.
- `tests/test_api.py` — NEW, HTTP-level, runs without Tesseract or an API key.

Design decisions worth knowing about:
- **Vision classifies; rules still govern safety.** `disposal_category`,
  `recovery_potential`, and `guidance_steps` come from the JSON rules engines
  no matter which tier classified. A damaged item is always `hazardous_waste`
  with damage steps — enforced in code.
- **Vision "Unknown" is not the end.** If the model can't tell what it is but
  OCR read a usable label, the keyword classifier still gets a shot. Any
  damage the model saw is preserved on that fallback result.
- **Battery chemistry is only claimed when it's printed.** Both tiers obey
  this: the vision prompt forbids inferring chemistry from shape; the keyword
  tier uses `ocr.fields.battery_type` only.
- **Effort default is `medium`** (`LABELWISE_VISION_EFFORT`) to keep a
  single-image call inside the PRD's ~15s target; raise to `high` if
  damage-detection recall matters more than latency.

## Still not built (documented, not forgotten)
- Analysis history, PDF export, location-aware guidance, rate limiting,
  batch upload — see README "Not built yet".

## Requires: system Tesseract binary
`pip install -r requirements.txt` installs the Python wrapper (`pytesseract`)
but NOT the OCR engine itself. Each machine running the backend needs
Tesseract installed separately:
- Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
- macOS: `brew install tesseract`
- Windows: installer from https://github.com/UB-Mannheim/tesseract/wiki
If Tesseract is missing, OCR silently degrades to "no text found" instead of
crashing the request — but the demo obviously needs it actually installed.

## Decision: dimension-limit message
PRD §3.2 defines a 4096×4096px dimension limit but no separate user-facing
message for it. Decision: it reuses `TOO_LARGE_MESSAGE` ("This image exceeds
the 5 MB upload limit.") since the PRD groups both under one "resource
limit" concept. Settled — not waiting on this.

## Run it (from the `labelwise/` directory)
```
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```
The pipeline itself is `services/pipeline.py` (plain function); the route
is a thin HTTP wrapper. The frontend can also run the pipeline in-process
(`LABELWISE_ANALYSIS_MODE=local`) — that's how the single-app Streamlit
Community Cloud deploy works; see README "Deploy for free".
Set `ANTHROPIC_API_KEY` to enable the vision tier; `GET /health` reports
`vision_enabled`.

## Run the tests
```
pytest backend/tests -v
```
`test_api.py` runs everywhere (OCR + vision mocked). `test_pipeline.py`
needs Tesseract and skips itself otherwise. Covers: each of the 13 categories' disposal/recovery mapping, OCR-blank and
gibberish -> unknown, damaged-item escalation to hazardous_waste for every
category, "unclaimed battery chemistry stays unknown" behavior, and the
validator's reject paths (oversized file, wrong extension, corrupt/spoofed
file).

## Endpoint

`GET /health`
Response: `{"status": "ok", "vision_enabled": true|false}`

`POST /analyze`
Request: `multipart/form-data`, field name `file` (image)
Success response (200):
```json
{
  "item": "Power Bank",
  "category": "Battery Electronics",
  "confidence": 0.94,
  "materials": [
    {"name": "Lithium-ion battery", "hazard": "high"},
    {"name": "Copper", "hazard": "low"}
  ],
  "damage_detected": false,
  "recovery_potential": "moderate",
  "disposal_category": "battery_recycling"
}
```
Error response (never a raw traceback), always HTTP 422 (validation/
uncertainty) or 500 (unexpected failure, caught by the global handler in
`main.py`):
```json
{"error": true, "message": "LabelWise couldn't complete the analysis. Please try again."}
```
The exact possible `message` strings (PRD §5): unsupported file type, file
too large (also covers oversized dimensions), poor image quality / no
useful text found, and the generic AI-failure message above.

## Contract notes for frontend
- `hazard` values are lowercase: `low | medium | high | critical | unknown`
  (`critical` is reserved for future damage-detection work — not emitted
  yet).
- `disposal_category` values are snake_case: `general_recyclable | e_waste | battery_recycling | hazardous_waste | specialized_recycling | reuse_refurbishment | unknown`
  (`reuse_refurbishment` is reserved for future reuse-recommendation work —
  not emitted yet).
- `recovery_potential`: `low | moderate | high | unknown`.
- `materials[].confidence`: `high | medium | low` (optional).
- `analysis_source`: `vision | keyword`.
- The original 7 fields will NOT change. New fields are additive and
  optional — see README "API contract" for the full success shape.
