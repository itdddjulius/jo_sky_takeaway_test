from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest
from pythonjsonlogger import jsonlogger

from app.models import AlertBatch
from app.store import AlertEngine

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logger = logging.getLogger("alert-service")
handler = logging.StreamHandler()
handler.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(handler)
logger.setLevel(LOG_LEVEL)

app = FastAPI(title="Alert Incident Service", version="1.0.0")
engine = AlertEngine()

alerts_received_counter = Counter("alerts_received_total", "Total alerts received")
alerts_processed_counter = Counter("alerts_processed_total", "Total alerts processed")
incidents_created_counter = Counter("incidents_created_total", "Total incidents created")
suppressed_counter = Counter("suppressed_duplicates_total", "Suppressed duplicate alerts")
suppression_rate_gauge = Gauge("suppression_rate", "Duplicate suppression rate")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/alerts/ingest")
def ingest_alerts(payload: AlertBatch):
    result = engine.ingest(payload.alerts)
    alerts_received_counter.inc(result.alerts_received)
    alerts_processed_counter.inc(result.alerts_processed)
    incidents_created_counter.inc(result.incidents_created)
    suppressed_counter.inc(result.suppressed_duplicates)
    suppression_rate_gauge.set(result.suppression_rate)
    logger.info(
        "alerts_ingested",
        extra={
            "alerts_received": result.alerts_received,
            "alerts_processed": result.alerts_processed,
            "suppressed_duplicates": result.suppressed_duplicates,
            "incidents_created": result.incidents_created,
            "incidents_updated": result.incidents_updated,
        },
    )
    return result.model_dump()


@app.post("/alerts/load-sample")
def load_sample_dataset():
    path = Path("/app/data/alerts.json")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sample dataset not found")
    data = json.loads(path.read_text())
    payload = AlertBatch.model_validate(data)
    return ingest_alerts(payload)


@app.get("/incidents")
def incidents():
    return {"incidents": [i.model_dump(mode="json") for i in engine.list_incidents()]}


@app.get("/metrics/summary")
def metrics_summary():
    return engine.metrics_summary().model_dump()


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return PlainTextResponse(generate_latest().decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
