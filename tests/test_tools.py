import pytest
import os

os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "fake-key-for-testing")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("OLLAMA_MODEL", "qwen3.5:4b")


def test_health_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_services():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.get("/services")
    assert response.status_code == 200
    names = [s["name"] for s in response.json()["services"]]
    assert "auth-service" in names


def test_incident_structure():
    incident = {
        "title": "Token validation failures",
        "service": "auth-service",
        "severity": "high",
        "symptoms": "Users unable to login",
        "root_cause": "Expired signing key",
        "resolution": "Rotated signing key",
        "tags": ["bad_deploy", "signing_key"],
    }
    assert incident["severity"] == "high"
    assert "bad_deploy" in incident["tags"]


def test_evidence_bundle_format():
    evidence_parts = [
        "=== search_logs ===\nFound 5 errors",
        "=== search_incidents ===\nFound 2 incidents",
    ]
    evidence = "\n\n".join(evidence_parts)
    assert "search_logs" in evidence
    assert "search_incidents" in evidence


def test_service_names_valid():
    valid = ["auth-service", "payment-service", "notification-service"]
    assert "auth-service" in valid
    assert "unknown-service" not in valid
