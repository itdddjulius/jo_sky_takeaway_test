from app.models import Alert
from app.store import AlertEngine


def test_deduplication_and_incident_creation():
    engine = AlertEngine()
    alerts = [
        Alert(timestamp="2026-03-24T10:00:00Z", service="payments", severity="critical", message="Database connection timeout after 3000ms on host pay-01", host="pay-01", region="eu-west-2"),
        Alert(timestamp="2026-03-24T10:01:00Z", service="payments", severity="critical", message="Database connection timeout after 3000ms on host pay-01", host="pay-01", region="eu-west-2"),
        Alert(timestamp="2026-03-24T10:02:00Z", service="payments", severity="critical", message="Database timed out after 3050ms on host pay-01", host="pay-01", region="eu-west-2"),
    ]
    result = engine.ingest(alerts)
    assert result.suppressed_duplicates == 1
    assert result.incidents_created == 1
    assert len(engine.list_incidents()) == 1
