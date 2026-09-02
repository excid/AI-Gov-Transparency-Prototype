"""HTTP boundary for peer-relative procurement anomaly scoring."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from queue import Queue
from threading import Thread
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from .anomaly import score_anomalies
from .data_prep import DataPreparationError, prepare_training_records
from .ocr import PdfExtractionError
from .tor_analysis import analyze_tor


class ScoreRequest(BaseModel):
    projects: list[dict[str, Any]] = Field(min_length=1, max_length=1000)
    bids: list[dict[str, Any]] = Field(default_factory=list, max_length=5000)
    costs: list[dict[str, Any]] = Field(default_factory=list, max_length=5000)


app = FastAPI(title="AI-Gov Transparency anomaly scorer", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
MAX_PDF_BYTES = 50 * 1024 * 1024


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze-tor")
async def analyze_tor_upload(file: UploadFile = File(...)) -> dict[str, Any]:
    if file.content_type != "application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="รองรับเฉพาะไฟล์ PDF")
    payload = await file.read(MAX_PDF_BYTES + 1)
    if len(payload) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF ต้องมีขนาดไม่เกิน 50 MB")
    try:
        return await run_in_threadpool(analyze_tor, payload, filename=file.filename)
    except PdfExtractionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _progress_stream(payload: bytes, filename: str | None):
    events: Queue[dict[str, Any] | None] = Queue()

    def report(stage: str, percent: int) -> None:
        events.put({"type": "progress", "stage": stage, "percent": percent})

    def run() -> None:
        try:
            result = analyze_tor(payload, filename=filename, on_progress=report)
            events.put({"type": "result", "data": result})
        except Exception as error:
            events.put({"type": "error", "message": str(error) or "วิเคราะห์ไม่สำเร็จ"})
        finally:
            events.put(None)

    yield json.dumps({"type": "progress", "stage": "received", "percent": 5}, ensure_ascii=False) + "\n"
    Thread(target=run, daemon=True).start()
    while (event := events.get()) is not None:
        yield json.dumps(event, ensure_ascii=False) + "\n"


@app.post("/analyze-tor/stream")
async def analyze_tor_stream(file: UploadFile = File(...)) -> StreamingResponse:
    if file.content_type != "application/pdf" and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="รองรับเฉพาะไฟล์ PDF")
    payload = await file.read(MAX_PDF_BYTES + 1)
    if len(payload) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF ต้องมีขนาดไม่เกิน 50 MB")
    return StreamingResponse(_progress_stream(payload, file.filename), media_type="application/x-ndjson")


@app.post("/score")
def score(request: ScoreRequest) -> dict[str, Any]:
    if len(request.projects) < 3:
        raise HTTPException(status_code=422, detail="ต้องมีโครงการอย่างน้อย 3 รายการเพื่อเปรียบเทียบ")
    try:
        frame = prepare_training_records(request.projects, request.bids, request.costs)
        results = score_anomalies(frame)
    except (DataPreparationError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    factors_by_id: dict[str, dict[str, float | int | None]] = {}
    for _, row in frame.iterrows():
        reference = row.get("reference_price_baht")
        agreed = row.get("agreed_price_baht")
        difference = None
        if reference is not None and reference > 0 and agreed is not None:
            difference = round(abs(reference - agreed) / reference * 100, 2)
        factors_by_id[str(row["project_id"])] = {
            "priceDifferencePercent": difference,
            "bidderCount": None if row.get("bidder_count") is None else int(row["bidder_count"]),
            "contractCount": int(row.get("contract_count", 0)),
            "missingCoreFieldCount": int(row.get("missing_core_field_count", 0)),
        }

    model_version = results[0].model_version
    return {
        "modelVersion": model_version,
        "cohortSize": len(results),
        "scoredAt": datetime.now(UTC).isoformat(),
        "scores": [
            {
                "projectId": result.project_id,
                "fiscalYear": result.fiscal_year,
                "rawScore": result.raw_score,
                "percentile": result.percentile,
                "factors": factors_by_id[result.project_id],
            }
            for result in results
        ],
    }
