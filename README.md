# Alert Incident Service

A small Python service that ingests alerts, suppresses duplicate noise, 
correlates related alerts into incidents, 
and suggests a simple automated action when alert volume crosses a threshold.

## 1. What this solution does

This solution implements all requested areas:

- **Alert correlation** using a clear, explainable rule set
- **Noise reduction** by suppressing repeated alerts within a deduplication window
- **Automation rule**: when more than **X alerts** from the same service occur within **Y minutes**, the API attaches a suggested action
- **Interface**: FastAPI endpoints and a CLI
- **Observability**: JSON logs, summary metrics, and Prometheus-compatible metrics
- **Design write-up**: included below in this README
- **Docker Compose deployment**: included

---

## 2. Project structure

```text
alert_incident_service/
├── app/
│   ├── cli.py
│   ├── correlation.py
│   ├── main.py
│   ├── models.py
│   └── store.py
├── data/
│   └── alerts.json
├── tests/
│   └── test_engine.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 3. Input dataset

The sample dataset is in `data/alerts.json` and includes:

- required fields: `timestamp`, `service`, `severity`, `message`, `host`, `region`
- exact duplicates
- slight message variations
- cascading failures
- irrelevant/noisy alerts

### Example records

```json
{
  "timestamp": "2026-03-24T10:00:00Z",
  "service": "payments",
  "severity": "critical",
  "message": "Database connection timeout after 3000ms on host pay-01",
  "host": "pay-01",
  "region": "eu-west-2"
}
```

```json
{
  "timestamp": "2026-03-24T10:02:00Z",
  "service": "checkout",
  "severity": "high",
  "message": "Payment authorization failed due to upstream database timeout",
  "host": "chk-02",
  "region": "eu-west-2"
}
```

These examples demonstrate both a primary failure and a cascading downstream failure.

---

## 4. Correlation approach and rationale

### Rule summary

Alerts are correlated into the same incident when all of the following are true:

1. **Same service**
2. **Same region**
3. **Within a time window** (default: 10 minutes)
4. One of these message conditions is true:
   - same normalized message
   - high message similarity (`SequenceMatcher >= 0.72`)
   - shared failure pattern (for example, database-related alerts)

### Message normalization

Before matching, alert messages are normalized to reduce meaningless differences.

The normalizer removes or standardizes:

- numeric IDs
- timing values such as `3000ms`
- host variations such as `pay-01`
- minor wording differences such as `timed out` vs `timeout`

### Concise example

These alerts are treated as related:

- `Database connection timeout after 3000ms on host pay-01`
- `Database timed out after 3050ms on host pay-01`
- `Database connection timeout after 2800ms on host pay-03`

Reason: once normalized, they all describe the same failure mode.

### Why this approach?

This design is intentionally simple and explainable. A reviewer can see exactly why alerts were grouped without needing a black-box model.

---

## 5. Noise reduction approach

### Deduplication rule

A duplicate is suppressed when the alert has the same fingerprint within the deduplication window (default: 5 minutes).

Fingerprint fields:

- service
- region
- host
- normalized message
- severity

### Concise example

If the same `payments` timeout alert appears at `10:00`, `10:01`, and `10:01:30`, only the first is processed and the next two are suppressed.

### Expected impact

- **Before**: all repeated alerts create operator noise
- **After**: duplicates are counted but not allowed to create more incidents

This directly improves signal-to-noise ratio.

---

## 6. Automation rule

### Implemented rule

> If more than **X alerts** from the same service occur within **Y minutes**, trigger a suggested action.

Default configuration:

- `X = 4`
- `Y = 10 minutes`

### Suggested action returned by the system

```text
AUTO-SUGGEST: Service 'search' exceeded 4 alerts in 10 minutes in region 'eu-west-2'.
Suggested action: restart the failing workload, scale replicas by +1, and open a ticket for on-call review.
```

### Concise example

If `search` emits 5 CPU alerts inside 10 minutes, the incident gets a suggested action because the system sees a sustained pattern, not a one-off event.

---

## 7. API interface

### Start the service

```bash
docker compose up --build
```

Service URL:

- `http://localhost:8000`

### Endpoints

#### Health check

```bash
curl http://localhost:8000/health
```

#### Ingest a custom alert batch

```bash
curl -X POST http://localhost:8000/alerts/ingest \
  -H "Content-Type: application/json" \
  -d @data/alerts.json
```

#### Load the bundled sample dataset

```bash
curl -X POST http://localhost:8000/alerts/load-sample
```

#### Query incidents

```bash
curl http://localhost:8000/incidents
```

#### Query summary metrics

```bash
curl http://localhost:8000/metrics/summary
```

#### Prometheus metrics

```bash
curl http://localhost:8000/metrics
```

---

## 8. CLI interface

The solution also includes a small CLI.

### Submit alerts

```bash
python -m app.cli submit --file data/alerts.json
```

### Query incidents

```bash
python -m app.cli incidents
```

### Query metrics summary

```bash
python -m app.cli metrics
```

---

## 9. Observability

This service exposes observability in two ways.

### A. Structured logs

The API writes JSON logs such as:

```json
{
  "message": "alerts_ingested",
  "alerts_received": 20,
  "alerts_processed": 15,
  "suppressed_duplicates": 5,
  "incidents_created": 6,
  "incidents_updated": 9
}
```

### B. Metrics

- `alerts_received_total`
- `alerts_processed_total`
- `incidents_created_total`
- `suppressed_duplicates_total`
- `suppression_rate`

### Why this matters

An operator can quickly answer:

- How many alerts arrived?
- How many were suppressed?
- How many incidents were created?
- Is suppression helping?

---

## 10. Walkthrough of the code

### `app/models.py`

Defines input/output schemas for:

- alerts
- alert batches
- incidents
- metrics

### `app/correlation.py`

Contains the explainable correlation logic:

- message normalization
- fingerprint generation
- similarity scoring
- correlation decision function

### `app/store.py`

Contains the in-memory alert engine responsible for:

- deduplication
- incident creation/update
- automation rule evaluation
- metrics accumulation

### `app/main.py`

FastAPI application exposing endpoints for:

- ingesting alerts
- loading the sample dataset
- listing incidents
- exposing metrics

### `app/cli.py`

Simple command line interface for local usage.

---

## 11. Example flow

### Step 1
Ingest the sample dataset.

```bash
curl -X POST http://localhost:8000/alerts/load-sample
```

### Step 2
The engine sorts alerts by timestamp.

### Step 3
For each alert:

- compute normalized message
- compute fingerprint
- suppress if duplicate
- otherwise attempt to correlate into an existing incident
- if no match exists, create a new incident
- evaluate the automation threshold for the service

### Step 4
Query incidents:

```bash
curl http://localhost:8000/incidents
```

### Concise example outcome

- Repeated `payments` DB timeout alerts collapse into one incident
- repeated exact duplicates are suppressed
- multiple `search` CPU alerts trigger a suggested action
- irrelevant `inventory` info alert remains low-priority noise and does not merge with other services

---

## 12. Trade-offs made

### Trade-off 1: In-memory store instead of database

**Why chosen:** keeps the exercise compact and easy to run.

**Cost:** incidents are lost on restart.

### Trade-off 2: Heuristic correlation instead of machine learning

**Why chosen:** easier to explain and debug in an interview.

**Cost:** less adaptive to unusual message patterns.

### Trade-off 3: Simple action suggestions instead of actual remediation

**Why chosen:** safer for a coding task.

**Cost:** the system recommends actions rather than executing them.

---

## 13. Limitations

- Incident state is not persisted
- Correlation is service/region centric and intentionally conservative
- Cascading failure correlation is basic rather than topology-aware
- The action engine suggests remediation but does not execute runbooks
- No authentication or multi-tenant controls are included because this is a focused technical exercise

---

## 14. How the system would scale

### Near-term scale path

1. Replace in-memory state with Redis or PostgreSQL
2. Add a queue such as Kafka or RabbitMQ for ingestion buffering
3. Partition incidents by service and region
4. Run multiple API replicas behind a load balancer
5. Export metrics to Prometheus + Grafana dashboards

### Concise example

A scalable production design could look like:

```text
Alert Sources -> API Gateway -> Queue -> Correlation Workers -> Incident Store -> API / Dashboard
```

This would let ingestion remain fast while correlation runs asynchronously.

---

## 15. How the solution could evolve using AI/ML

### A. Smarter message similarity
Use sentence embeddings instead of string matching so the system can understand that:

- `database timeout`
- `postgres unreachable`
- `payment DB not responding`

may all refer to the same issue.

### B. Root-cause suggestion
Train a model on prior incidents so the system can predict likely root cause and preferred remediation.

### C. Noise classification
Use ML to classify alerts into:

- actionable
- informational
- noisy
- maintenance related

### D. Topology-aware correlation
Use service dependency graphs plus AI reasoning to link downstream checkout failures to an upstream payments outage.

### Concise example

Today: string rules say two alerts are similar.

Future: an embedding model says they are semantically the same even if they share very few words.

---

## 16. Interview walkthrough talking points

For the 45-minute follow-up, a strong walkthrough structure is:

1. Explain the input dataset and the kinds of noise it contains
2. Show how normalization works
3. Show the deduplication fingerprint logic
4. Show the incident correlation rules
5. Show the automation threshold logic
6. Demo `/alerts/load-sample`
7. Demo `/incidents`
8. Demo `/metrics/summary`
9. Discuss trade-offs, limitations, and scaling path
10. Close with how AI/ML would improve correlation and root-cause analysis

---

## 17. Running tests

```bash
docker compose run --rm alert-service pytest
```

---

## 18. Suggested submission note

The original prompt asks for return by email before interview scheduling. Since email sending is outside this codebase, the recommended submission package is:

- source code ZIP
- README walkthrough
- sample dataset
- short demo notes

A concise cover note could be:

> Attached is my Python + Docker Compose alert correlation solution. It includes a sample dataset, API/CLI interface, observability, duplicate suppression, incident grouping, automation suggestions, and a detailed design walkthrough in the README.

---

## 19. Quick demo commands

```bash
docker compose up --build
curl -X POST http://localhost:8000/alerts/load-sample
curl http://localhost:8000/incidents | jq
curl http://localhost:8000/metrics/summary | jq
```

---

## 20. Summary

This solution is intentionally pragmatic:

- simple to run
- simple to explain
- easy to extend
- demonstrates correlation, suppression, automation, interface design, observability, and architectural thinking

It is suitable for a coding interview because it balances implementation quality with explainability.
