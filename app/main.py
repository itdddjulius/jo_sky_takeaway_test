from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse
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


@app.get("/", response_class=HTMLResponse)
def root():
    summary = engine.metrics_summary().model_dump()

    return f"""
    <html>
      <head>
        <title>Alert Incident Service</title>
        <style>
          body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            background: #0f172a;
            color: #e2e8f0;
          }}
          .card {{
            background: #1e293b;
            padding: 24px;
            border-radius: 12px;
            max-width: 900px;
          }}
          a {{
            color: #38bdf8;
            text-decoration: none;
          }}
          button {{
            padding: 10px 16px;
            margin: 6px;
            border-radius: 8px;
            border: none;
            background: #22c55e;
            color: #000;
            font-weight: bold;
            cursor: pointer;
          }}
          button:hover {{
            background: #4ade80;
          }}
          pre {{
            background: #020617;
            padding: 12px;
            border-radius: 8px;
            max-height: 300px;
            overflow: auto;
          }}
        </style>
      </head>

      <body>
        <div class="card">
          <h1>Alert Incident Service</h1>
          <p>Service is running successfully.</p>

          <h2>Quick Links</h2>
          <ul>
            <li><a href="/health">/health</a></li>
            <li><a href="/incidents">/incidents</a></li>
            <li><a href="/metrics/summary">/metrics/summary</a></li>
            <li><a href="/metrics">/metrics</a></li>
            <li><a href="/docs">/docs</a></li>
          </ul>

          <h2>Metrics Snapshot</h2>
          <ul>
            <li>alerts_received_total: {summary["alerts_received_total"]}</li>
            <li>alerts_processed_total: {summary["alerts_processed_total"]}</li>
            <li>incidents_created_total: {summary["incidents_created_total"]}</li>
            <li>suppressed_duplicates_total: {summary["suppressed_duplicates_total"]}</li>
            <li>suppression_rate: {summary["suppression_rate"]}</li>
          </ul>

          <h2>Actions</h2>
          <button onclick="loadSample()">LOAD-SAMPLE</button>
          <button onclick="getIncidents()">INCIDENTS</button>
          <button onclick="getSummary()">SUMMARY</button>
          <button onclick="window.location.href='/docs'">DOCS</button>

          <h2>Response</h2>
          <pre id="output">Click a button to execute...</pre>
        </div>

        <script>
          async function loadSample() {{
            setOutput("Loading sample alerts...");
            try {{
              const res = await fetch('/alerts/load-sample', {{ method: 'POST' }});
              const data = await res.json();
              setOutput(JSON.stringify(data, null, 2));
            }} catch (err) {{
              setOutput("Error: " + err);
            }}
          }}

          async function getIncidents() {{
            setOutput("Fetching incidents...");
            try {{
              const res = await fetch('/incidents');
              const data = await res.json();
              setOutput(JSON.stringify(data, null, 2));
            }} catch (err) {{
              setOutput("Error: " + err);
            }}
          }}

          async function getSummary() {{
            setOutput("Fetching summary...");
            try {{
              const res = await fetch('/metrics/summary');
              const data = await res.json();
              setOutput(JSON.stringify(data, null, 2));
            }} catch (err) {{
              setOutput("Error: " + err);
            }}
          }}

          function setOutput(text) {{
            document.getElementById("output").textContent = text;
          }}
        </script>
      </body>
    </html>
    """


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