from __future__ import annotations

import os
import uuid
from collections import defaultdict, deque
from datetime import timedelta
from typing import Deque

from app.correlation import can_correlate, fingerprint, highest_severity, normalize_message
from app.models import Alert, Incident, IncidentAlert, IngestResponse, MetricsResponse


class AlertEngine:
    def __init__(self) -> None:
        self.correlation_window_minutes = int(os.getenv("CORRELATION_WINDOW_MINUTES", "10"))
        self.dedup_window_minutes = int(os.getenv("DEDUP_WINDOW_MINUTES", "5"))
        self.automation_threshold_x = int(os.getenv("AUTOMATION_THRESHOLD_X", "4"))
        self.automation_window_y_minutes = int(os.getenv("AUTOMATION_WINDOW_Y_MINUTES", "10"))

        self.incidents: list[Incident] = []
        self.recent_fingerprints: dict[str, Deque] = defaultdict(deque)
        self.recent_service_alerts: dict[str, Deque] = defaultdict(deque)
        self.metrics = {
            "alerts_received_total": 0,
            "alerts_processed_total": 0,
            "incidents_created_total": 0,
            "suppressed_duplicates_total": 0,
        }

    def _evict_old(self, dq: Deque, current_ts, minutes: int) -> None:
        while dq and current_ts - dq[0] > timedelta(minutes=minutes):
            dq.popleft()

    def _is_duplicate(self, alert: Alert) -> tuple[bool, int, str]:
        fp = fingerprint(alert)
        dq = self.recent_fingerprints[fp]
        self._evict_old(dq, alert.timestamp, self.dedup_window_minutes)
        if dq:
            dq.append(alert.timestamp)
            return True, len(dq), fp
        dq.append(alert.timestamp)
        return False, len(dq), fp

    def _suggest_action(self, service: str, region: str) -> str | None:
        dq = self.recent_service_alerts[service]
        if len(dq) >= self.automation_threshold_x:
            return (
                f"AUTO-SUGGEST: Service '{service}' exceeded {self.automation_threshold_x} alerts in "
                f"{self.automation_window_y_minutes} minutes in region '{region}'. Suggested action: "
                f"restart the failing workload, scale replicas by +1, and open a ticket for on-call review."
            )
        return None

    def ingest(self, alerts: list[Alert]) -> IngestResponse:
        alerts = sorted(alerts, key=lambda a: a.timestamp)
        received = len(alerts)
        processed = 0
        suppressed = 0
        created = 0
        updated = 0
        self.metrics["alerts_received_total"] += received

        for alert in alerts:
            is_dup, dup_count, fp = self._is_duplicate(alert)
            if is_dup:
                suppressed += 1
                self.metrics["suppressed_duplicates_total"] += 1
                continue

            service_q = self.recent_service_alerts[alert.service]
            self._evict_old(service_q, alert.timestamp, self.automation_window_y_minutes)
            service_q.append(alert.timestamp)

            normalized = normalize_message(alert.message)
            incident_alert = IncidentAlert(
                timestamp=alert.timestamp,
                service=alert.service,
                severity=alert.severity,
                message=alert.message,
                host=alert.host,
                region=alert.region,
                normalized_message=normalized,
                fingerprint=fp,
                duplicate_count=dup_count,
                suppressed=False,
            )

            matched = None
            reason = ""
            for incident in reversed(self.incidents):
                ok, reason = can_correlate(alert, incident, self.correlation_window_minutes)
                if ok:
                    matched = incident
                    break

            if matched:
                matched.alerts.append(incident_alert)
                matched.updated_at = alert.timestamp
                matched.hosts = sorted(set([*matched.hosts, alert.host]))
                matched.severity = highest_severity([matched.severity, alert.severity])
                matched.correlation_reason = reason
                matched.suggested_action = self._suggest_action(alert.service, alert.region)
                updated += 1
            else:
                incident = Incident(
                    incident_id=str(uuid.uuid4()),
                    created_at=alert.timestamp,
                    updated_at=alert.timestamp,
                    service=alert.service,
                    region=alert.region,
                    hosts=[alert.host],
                    severity=alert.severity,
                    root_signature=normalized,
                    correlation_reason="new incident: no eligible prior incident",
                    alerts=[incident_alert],
                    suggested_action=self._suggest_action(alert.service, alert.region),
                )
                self.incidents.append(incident)
                created += 1
                self.metrics["incidents_created_total"] += 1

            processed += 1
            self.metrics["alerts_processed_total"] += 1

        suppression_rate = round((suppressed / received), 4) if received else 0.0
        return IngestResponse(
            alerts_received=received,
            alerts_processed=processed,
            suppressed_duplicates=suppressed,
            incidents_created=created,
            incidents_updated=updated,
            suppression_rate=suppression_rate,
        )

    def list_incidents(self) -> list[Incident]:
        return sorted(self.incidents, key=lambda i: i.updated_at, reverse=True)

    def metrics_summary(self) -> MetricsResponse:
        received = self.metrics["alerts_received_total"]
        suppressed = self.metrics["suppressed_duplicates_total"]
        suppression_rate = round((suppressed / received), 4) if received else 0.0
        return MetricsResponse(
            alerts_received_total=received,
            alerts_processed_total=self.metrics["alerts_processed_total"],
            incidents_created_total=self.metrics["incidents_created_total"],
            suppressed_duplicates_total=suppressed,
            suppression_rate=suppression_rate,
        )
