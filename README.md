# AI Gov Transparency Prototype

A hackathon prototype that helps reviewers screen Thai procurement TOR documents for competition-risk signals. It combines OCR, rule-based checks, historical-project comparison, and optional LLM-assisted extraction. Results are decision support only: they identify evidence for human review and do not determine corruption or legal liability.

## Prerequisites

- Docker Desktop with Docker Compose, or Node.js 22.13+ and Python 3.12
- API credentials for the GovSpending data source and an OpenAI-compatible LLM endpoint when those integrations are used
- At least 6 GB of memory available to the OCR/backend container

## Configuration

Copy `.env.example` to `.env`, then replace the placeholder API credentials. Never commit `.env` or files under `secrets/`.

```powershell
Copy-Item .env.example .env
```

## Run with Docker

```powershell
docker compose up --build
```

Open `http://localhost:3000`. The analysis API is available at `http://localhost:8000`, and its health endpoint is `http://localhost:8000/health`.

## Run without Docker

Backend:

```powershell
cd backend
uv sync
uv run uvicorn ai_gov_transparency.service:app --reload --host 127.0.0.1 --port 8000
```

Frontend, in a second terminal from the repository root:

```powershell
npm ci
npm run dev
```

For a local production build, run `npm run build` followed by `npm start`.

## Tests

```powershell
npm test
cd backend
uv run python -m unittest discover -s tests
```

## Architecture

- `app/` and `components/`: web interface and local API proxy
- `backend/ai_gov_transparency/`: OCR, TOR extraction, rules, similarity scoring, and FastAPI service
- `backend/data/models/`: trained prototype similarity/anomaly model
- `backend/tests/` and `tests/`: backend and frontend test suites

The similarity ranking prioritizes procurement type, then structural fields, then project-name similarity. The prototype model and thresholds require validation on representative labeled procurement data before production use.

## Contributing

Keep credentials outside Git, add tests for behavioral changes, and run both test suites before opening a pull request. Preserve page-level evidence references in analysis results so reviewers can verify every warning against the uploaded TOR.
