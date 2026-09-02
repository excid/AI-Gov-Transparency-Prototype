# AI-GOV Transparency Prototype — Engineering Handoff

## Purpose

This prototype helps Thai public-procurement reviewers screen Terms of Reference (TOR) PDFs for competition-limiting conditions. It combines page-preserving OCR, deterministic rules, optional LLM interpretation, and an unsupervised comparison against historical GovSpending projects. Findings are review signals with evidence and page references; they are not corruption determinations.

Primary users are procurement reviewers, auditors, and public-sector teams. Businesses assessing whether to bid are a secondary audience. The interface and analysis messages are primarily Thai.

## Architecture

The repository has two runtime services:

1. **Web (`/`)** — React 19 rendered through vinext/Vite with a Next-compatible app structure. `app/page.tsx` owns the single-page upload/results experience. In Docker it calls the Python service directly through `NEXT_PUBLIC_ANALYSIS_URL`.
2. **Analysis API (`backend/`)** — FastAPI performs PDF validation, OCR, rules, optional Qwen-compatible LLM analysis, feature extraction, and Isolation Forest scoring. It exposes both TOR analysis and a separate raw GovSpending cohort-scoring endpoint.

The normal interactive data path is:

```text
Browser -> IndexedDB cache lookup -> POST PDF to FastAPI /analyze-tor/stream
        -> embedded PDF text / local OCR -> optional LLM -> rules + features + ML
        <- NDJSON progress and final result -> results UI -> IndexedDB cache write
```

`app/api/analyze-tor/route.ts` is a non-streaming web-to-backend proxy for `POST /analyze-tor`. It validates PDF extension and size, forwards to `ML_SERVICE_URL`, and has a 300-second timeout. The current UI always appends `/stream`, so this proxy is not a complete fallback for the UI unless a matching `/api/analyze-tor/stream` handler is added or the client behavior is changed.

No database is used by the application pipeline. Uploaded files and OCR text are held in memory and are not persisted server-side. The browser may persist final analysis results in IndexedDB.

## OCR, Rule, LLM, and ML Pipeline

### 1. PDF validation and extraction

`ocr.extract_pdf_pages` rejects non-PDF bytes, encrypted PDFs, empty PDFs, and PDFs over 100 pages. HTTP upload routes separately enforce a 50 MB limit.

For each page, pypdf first extracts embedded text. A page with fewer than 40 extracted characters is considered missing and sent to OCR. Page numbers are retained throughout.

`local_ocr.local_paddle_pages` renders only those weak pages as JPEGs through Poppler, in groups of up to eight. PaddleOCR PP-OCRv5 (`lang="th"`, CPU) is the primary recognizer. Batch failures are retried one page at a time; Paddle misses fall back to Tesseract with `tha+eng`. OCR quality is a simple visible-alphanumeric density score, capped at 1.0, rather than a calibrated recognition-confidence score.

### 2. Deterministic rules

`tor_rules.evaluate_rules` normalizes Thai digits and emits evidence-preserving findings for six categories:

- previous-work value at least 50% of the project budget (high at 80% or above);
- a brand/model requirement without an allowed equivalent;
- a specific certificate or standard requiring human necessity review;
- three or more narrow numeric/technology constraints on a page;
- personnel experience of at least 10 years or at least three projects (high at 20 years);
- other restrictive phrases such as a same-contract requirement or “เฉพาะผู้ที่”.

Each finding includes category, severity, source (`rule`), source paragraph, page, Thai reason, confidence, and optional numeric details. Regex matching is intentionally transparent but context-limited.

### 3. Optional LLM analysis

`tor_llm.analyze_with_llm` runs only when both `LLM_API_KEY` and `LLM_BASE_URL` are set. It calls an OpenAI-compatible `POST {LLM_BASE_URL}/chat/completions`, defaulting to Alibaba Qwen model `qwen3.8-flash`, temperature 0, JSON-object response mode, 4,000 output tokens, and a 240-second timeout. Combined page text is truncated to 160,000 characters.

The parser accepts at most 20 findings, restricts categories and severities to the rule vocabulary, requires Thai summaries/reasons, and validates page, evidence, and confidence. Any missing configuration, request error, or schema failure degrades to rules plus ML and adds a visible warning; the API does not fail the whole analysis.

### 4. Pre-award feature extraction and ML

`tor_features.extract_preaward_features` extracts only information expected to exist before award:

- log-transformed budget;
- reference-price-to-budget ratio;
- log-transformed duration in days;
- count of missing core fields;
- inferred project type (`งานก่อสร้าง` only);
- inferred purchase method (`e-bidding` only);
- Thai fiscal year when present.

The bundled artifact is a sampled historical GovSpending dataframe, not a serialized fitted estimator. For every TOR request, `tor_model.score_preaward` selects a cohort, fits median imputation and robust scaling, then fits a 150-tree Isolation Forest to that cohort. The TOR receives a high-is-unusual percentile relative to cohort scores.

ML abstains when fewer than two of budget, reference ratio, and duration are available, or when the artifact file is missing. Model training requires at least 30 historical records. `backend/data/models/tor-isolation-forest.joblib` is the default bundled artifact and has contract version `tor-isolation-forest-0.1`.

Rules run before model result assembly, but progress is reported as `ocr` (15%), `llm` (60%), `screening` (90%), and `complete` (100%). The streaming HTTP layer emits `received` (5%) before those events.

### 5. Reconciliation

Rule and LLM findings are sorted by page/category, with rule findings first. Findings sharing the same category and page are deduplicated, so a rule finding wins over an LLM finding for that pair even if the evidence differs. The final response reports warnings for absent LLM, ML abstention, and any OCR page with quality below 0.5.

## Similar-Project Ranking

The model narrows historical rows in this order when each narrowed cohort still contains at least 30 records:

1. matching inferred project type;
2. matching purchase method;
3. budget between 0.5× and 2× the TOR budget.

If no narrowing criterion can retain 30 rows, the full sampled dataset is used. Applied labels are returned in `comparable_criteria`.

Historical and TOR numeric features are median-imputed and robust-scaled. The three rows with the smallest Euclidean distance from the TOR are returned as `similar_projects`. Displayed similarity is `100 / (1 + distance)`, rounded to one decimal. It is a convenience score, not a probability, semantic similarity, or validated relevance metric. Ranking does not directly use department, fiscal year, or free-text content.

## API Contracts

### `GET /health`

Returns HTTP 200:

```json
{ "status": "ok" }
```

### `POST /analyze-tor`

Multipart form with field `file`. Accepts a PDF by MIME type or `.pdf` filename, up to 50 MB. Returns 415 for unsupported type, 413 for size, and 422 for extraction errors.

Successful response fields:

```text
status: "completed" | "completed_with_warnings"
summary: string
pageCount: number
ocrPages: number
findings: Finding[]
features: {
  log_budget, reference_to_budget_ratio, log_duration_days: number | null
  missing_core_field_count: number
  project_type_name, purchase_method_name: string | null
  fiscal_year: number | null
}
model: {
  abstained: boolean
  reason: string
  percentile, raw_score: number | null
  model_version: string
  cohort_size: number
  comparable_criteria: string[]
  similar_projects: SimilarProject[]
}
warnings: string[]
disclaimer: string
documentId: string (first 16 hex characters of the PDF SHA-256)
```

`Finding` contains `category`, `severity` (`low|medium|high`), `source` (`rule|llm`), `evidence`, `page`, `reason`, `confidence`, and `details`.

`SimilarProject` contains `project_id`, `department`, `fiscal_year`, `budget_baht`, `purchase_method`, `project_type`, `duration_days`, and `similarity_percent`.

### `POST /analyze-tor/stream`

Uses the same multipart input and size/type validation. Response media type is `application/x-ndjson`, one JSON object per line:

```json
{ "type": "progress", "stage": "received|ocr|llm|screening|complete", "percent": 5 }
{ "type": "result", "data": { "...": "same analysis body as above" } }
{ "type": "error", "message": "human-readable error" }
```

Pipeline errors after streaming begins are represented by an `error` event rather than an HTTP error status.

### `POST /score`

This separate endpoint scores 3–1,000 raw GovSpending project records, with optional `bids` and `costs` arrays of up to 5,000 each:

```json
{
  "projects": [{ "project_id": "P-001", "year": 2568, "project_money": 1000000 }],
  "bids": [],
  "costs": []
}
```

It prepares post-award and metadata features, fits a cohort Isolation Forest, and returns `modelVersion`, `cohortSize`, UTC `scoredAt`, and a score per project with `projectId`, `fiscalYear`, `rawScore`, `percentile`, and factors (`priceDifferencePercent`, `bidderCount`, `contractCount`, `missingCoreFieldCount`). Invalid or undersized cohorts return 422.

## Frontend Flow

1. User selects a PDF; the UI shows name and size and enables analysis.
2. The browser reads the file bytes and computes a versioned SHA-256 cache key.
3. Unless forced, it checks IndexedDB. A hit immediately renders the result and marks it as cached.
4. A miss sends multipart form data to `{NEXT_PUBLIC_ANALYSIS_URL}/stream` and incrementally decodes NDJSON.
5. The UI shows stage, percentage, elapsed seconds, and an OCR-specific latency note.
6. Results show a summary, page/OCR counts, severity counts, expandable evidence/reasons, and source labels distinguishing rules from LLM findings.
7. A second tab shows up to three similar projects and the model percentile/cohort context.
8. Warnings are grouped under a disclosure. Cached results offer a force-reanalysis button; users can reset to analyze another file.

The current client-side TypeScript `Analysis` type omits some backend fields (`status`, `features`, `documentId`, and parts of `model`) but safely ignores them at runtime.

## Caching

`lib/analysis-cache.ts` stores complete response objects in browser IndexedDB database `ai-gov-transparency`, object store `analyses`. Keys are:

```text
{pipelineVersion}:{SHA-256 of exact PDF bytes}
```

The hard-coded frontend pipeline version is `paddle-th-rules-ml-qwen-v4-similar-projects`; changing it invalidates prior results without deleting them. There is no TTL, eviction policy, schema migration, server cache, or user/account namespace. Private browsing/storage failures are swallowed so analysis can continue. Force reanalysis bypasses reads and overwrites the same versioned key after success.

## Docker Setup

Intended startup from repository root:

```powershell
docker compose up --build
```

Expected services:

- web: `http://localhost:3000`
- analysis API: `http://localhost:8000`
- health check: `http://localhost:8000/health`

The web image uses Node 22 and runs the development server on `0.0.0.0:3000`. The backend uses Python 3.12, installs Poppler and Thai/English Tesseract packages, installs the Python project, copies the model artifact, and starts Uvicorn on port 8000. A named `paddle-models` volume preserves Paddle model downloads under `/root/.paddlex`.

Important current issue: `backend/Dockerfile` runs `COPY pyproject.toml uv.lock ./`, but `backend/uv.lock` is absent from this repository. A clean backend image build will fail until the lockfile is added or that copy line is changed.

The backend CORS allowlist permits only `http://localhost:3000` and `http://127.0.0.1:3000`.

## Environment Variables

No secret values belong in this document or source control. Root `.env` is ignored and is loaded into the `ml` container by Compose.

| Variable | Service | Purpose / default |
| --- | --- | --- |
| `LLM_API_KEY` | backend | Secret bearer token; absent disables LLM analysis. |
| `LLM_BASE_URL` | backend | OpenAI-compatible API base URL; absent disables LLM analysis. |
| `LLM_MODEL` | backend | Chat-completions model; defaults to `qwen3.8-flash` and Compose sets the same value. |
| `TOR_MODEL_PATH` | backend | Historical artifact path; defaults to `data/models/tor-isolation-forest.joblib`, Compose uses `/app/data/models/tor-isolation-forest.joblib`. |
| `OCR_RENDER_DPI` | backend | Paddle page-render DPI; default `180`. |
| `OCR_JPEG_QUALITY` | backend | Paddle JPEG quality; default `88`. |
| `OCR_DPI` | backend | Tesseract fallback render DPI; default `150`. |
| `OCR_PSM` | backend | Tesseract page-segmentation mode; default `6`. |
| `TESSERACT_CMD` | backend | Optional explicit Tesseract executable path, mainly for local Windows runs. |
| `GOVSPENDING_API_KEY` | backend CLI | Secret used only by `fetch-projects`. |
| `ML_SERVICE_URL` | web server | Base URL used by the non-streaming Next proxy; default `http://127.0.0.1:8000`, Compose sets `http://ml:8000`. |
| `NEXT_PUBLIC_ANALYSIS_URL` | browser build/runtime | Public base URL used by the UI; defaults to `/api/analyze-tor`, Compose sets `http://localhost:8000/analyze-tor`. |

`OCR_API` exists in the local environment file but is not referenced by current source code.

## Important Files

- `PRODUCT.md` — product intent, users, principles, and positioning constraints.
- `app/page.tsx` — complete upload, streaming, progress, result, warning, and similar-project UI.
- `app/globals.css` — page styling and responsive behavior.
- `app/api/analyze-tor/route.ts` — non-streaming server proxy and upload validation.
- `lib/analysis-cache.ts` — versioned browser cache and IndexedDB adapter.
- `lib/progress-stream.ts` — incremental NDJSON decoder.
- `backend/ai_gov_transparency/service.py` — FastAPI routes and streaming boundary.
- `backend/ai_gov_transparency/tor_analysis.py` — end-to-end orchestration, fallback handling, and finding reconciliation.
- `backend/ai_gov_transparency/ocr.py` — PDF parsing, page selection, quality, Tesseract fallback, and document ID.
- `backend/ai_gov_transparency/local_ocr.py` — rendering, PaddleOCR, retry, and fallback behavior.
- `backend/ai_gov_transparency/tor_rules.py` — six deterministic rule families.
- `backend/ai_gov_transparency/tor_llm.py` — LLM prompt, request, and strict output validation.
- `backend/ai_gov_transparency/tor_features.py` — pre-award TOR feature extraction.
- `backend/ai_gov_transparency/tor_model.py` — artifact contract, cohort selection, anomaly score, and similar projects.
- `backend/ai_gov_transparency/data_prep.py` — GovSpending JSON/JSONL/CSV ingestion and feature preparation.
- `backend/ai_gov_transparency/anomaly.py` — generic `/score` cohort model.
- `backend/ai_gov_transparency/cli.py` — fetch, prepare, and train commands.
- `backend/data/models/tor-isolation-forest.joblib` — bundled historical comparison artifact.
- `docker-compose.yml`, `Dockerfile`, `backend/Dockerfile` — local two-service deployment.

## Tests

Backend tests are standard-library `unittest` tests and cover data preparation, generic anomaly scoring, OCR page preservation/retries/result parsing, all six rule families, LLM schema constraints, pre-award features, model abstention/versioning/reproducibility/similar projects, pipeline degradation/deduplication/progress, and HTTP validation/streaming/scoring.

Run from repository root:

```powershell
Set-Location backend
python -m unittest discover -s tests -v
```

Frontend unit tests use Node's built-in test runner and cover versioned cache keys plus split/malformed NDJSON handling:

```powershell
node --test tests/analysis-cache.test.ts tests/progress-stream.test.ts
```

Static checks and build:

```powershell
npm run lint
npm run build
```

`package.json` currently has no `test` script. Tests are mostly unit/contract tests with mocks; there is no browser E2E test, real OCR fixture suite, live LLM integration test, Docker smoke test, or measured accuracy benchmark.

## Known Limitations

- This is a review aid, not a corruption classifier; no production accuracy, customer, or performance claims have been established.
- Rule extraction is regex-based and supports a narrow Thai vocabulary. It can miss paraphrases and can flag legitimate requirements without full legal/domain context.
- LLM evidence is schema-validated but not checked to confirm that the quoted string occurs on the declared PDF page.
- LLM input truncates at 160,000 characters, potentially omitting later pages from LLM review while rules still see all extracted pages.
- OCR is CPU-heavy and synchronous inside a worker thread. There is no queue, cancellation, concurrency limit, or per-page progress.
- OCR “quality” is character density, not confidence. Paddle failures are mostly swallowed and may surface only as missing/low-quality text.
- The model is unsupervised, retrained per request, and based on a sampled artifact. Percentile and similarity values are descriptive, not calibrated risk probabilities.
- Cohort filters use substring matching and only apply when 30 rows remain. Fiscal year and department do not constrain TOR cohorts.
- Similar-project ranking uses only four transformed numeric features; metadata is display-only after selection.
- Rule/LLM deduplication by category plus page can discard a distinct finding on the same page.
- Browser cache has no expiry or deletion UI and retains prior pipeline versions until browser data is cleared.
- Direct browser-to-backend deployment requires the frontend to reach port 8000 and satisfy the hard-coded CORS allowlist. The relative proxy fallback does not currently stream.
- API docs are disabled (`docs_url=None`, `redoc_url=None`), and there is no authentication, rate limiting, audit log, malware scanning, or tenant isolation.
- Frontend upload validation relies mostly on the API; it displays a 50 MB limit but does not reject oversized files before hashing/upload.
- `next.config.ts` sets a server-action body limit, but the active client flow does not use a server action.
- The backend Docker build currently references a missing `uv.lock`.

## Next Steps

1. Fix and smoke-test Docker reproducibility: add a generated `backend/uv.lock` or remove it from the Docker copy step, then verify health, OCR model persistence, and a real PDF analysis.
2. Choose one production request topology. Either add a streaming same-origin proxy and use relative URLs, or configure direct API access with deployment-specific CORS and public URLs.
3. Add representative Thai TOR fixtures (native text and scans), golden page/evidence expectations, OCR quality measurements, and end-to-end browser tests.
4. Verify LLM evidence against normalized page text and report rejected/hallucinated citations; consider chunking long documents instead of character truncation.
5. Version the whole response contract and derive the frontend cache version from backend/model/rule versions rather than a manually edited string.
6. Benchmark rule precision/recall and ML stability on a human-reviewed dataset. Define explicit abstention and escalation thresholds before showing severity as operational risk.
7. Improve cohort construction and nearest-project explanations, including fiscal-year relevance, categorical distance, and per-feature contribution displays.
8. Add operational controls appropriate to deployment: authentication, rate limiting, upload scanning, timeouts/cancellation, structured logs without document text, and retention/privacy policy.
9. Add cache management (TTL, delete/clear controls, quota handling) and clarify on-device persistence in the UI.
10. Expose or generate an API schema, align frontend types with it, and add contract tests covering both JSON and NDJSON endpoints.
