from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import timedelta
from difflib import SequenceMatcher
from typing import Iterable

from app.models import Alert, Incident

VOLATILE_PATTERNS = [
    re.compile(r"\b\d+\b"),
    re.compile(r"\b(?:[a-f0-9]{8,}|[A-Z0-9]{8,})\b", re.IGNORECASE),
    re.compile(r"host[-_ ]?\w+", re.IGNORECASE),
    re.compile(r"node[-_ ]?\w+", re.IGNORECASE),
    re.compile(r"timeout after \d+ms", re.IGNORECASE),
]

SEVERITY_RANK = {"critical": 4, "high": 3, "error": 3, "warning": 2, "info": 1, "low": 1}


def normalize_message(message: str) -> str:
    text = message.lower().strip()
    for pattern in VOLATILE_PATTERNS:
        text = pattern.sub("<var>", text)
    text = re.sub(r"\s+", " ", text)
    replacements = {
        "timed out": "timeout",
        "connection refused": "connect_refused",
        "db": "database",
        "cpu usage": "cpu",
        "disk usage": "disk",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def message_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def fingerprint(alert: Alert) -> str:
    normalized = normalize_message(alert.message)
    raw = f"{alert.service}|{alert.region}|{alert.host}|{normalized}|{alert.severity.lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def root_signature(alerts: Iterable[Alert]) -> str:
    normalized_messages = [normalize_message(a.message) for a in alerts]
    if not normalized_messages:
        return "unknown"
    top = Counter(normalized_messages).most_common(1)[0][0]
    return top


def highest_severity(values: Iterable[str]) -> str:
    values = list(values)
    if not values:
        return "info"
    return max(values, key=lambda v: SEVERITY_RANK.get(v.lower(), 0))


def can_correlate(alert: Alert, incident: Incident, correlation_window_minutes: int) -> tuple[bool, str]:
    window = timedelta(minutes=correlation_window_minutes)
    if alert.service != incident.service:
        return False, "different service"
    if alert.region != incident.region:
        return False, "different region"
    if alert.timestamp - incident.updated_at > window:
        return False, "outside time window"

    normalized = normalize_message(alert.message)
    if normalized == incident.root_signature:
        return True, "same normalized message within time window"

    similarities = [message_similarity(normalized, a.normalized_message) for a in incident.alerts[-5:]]
    if similarities and max(similarities) >= 0.72:
        return True, "similar message within time window"

    if any("database" in x.normalized_message for x in incident.alerts) and "database" in normalized:
        return True, "shared database failure pattern"

    return False, "insufficient similarity"
