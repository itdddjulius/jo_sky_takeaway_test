from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Alert(BaseModel):
    timestamp: datetime
    service: str
    severity: str
    message: str
    host: str
    region: str


class AlertBatch(BaseModel):
    alerts: List[Alert] = Field(default_factory=list)


class IncidentAlert(BaseModel):
    timestamp: datetime
    service: str
    severity: str
    message: str
    host: str
    region: str
    normalized_message: str
    fingerprint: str
    duplicate_count: int = 0
    suppressed: bool = False


class Incident(BaseModel):
    incident_id: str
    created_at: datetime
    updated_at: datetime
    service: str
    region: str
    hosts: List[str]
    severity: str
    root_signature: str
    correlation_reason: str
    alerts: List[IncidentAlert] = Field(default_factory=list)
    suggested_action: Optional[str] = None


class IngestResponse(BaseModel):
    alerts_received: int
    alerts_processed: int
    suppressed_duplicates: int
    incidents_created: int
    incidents_updated: int
    suppression_rate: float


class MetricsResponse(BaseModel):
    alerts_received_total: int
    alerts_processed_total: int
    incidents_created_total: int
    suppressed_duplicates_total: int
    suppression_rate: float
