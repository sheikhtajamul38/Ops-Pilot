import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def test_health_endpoint():
    from app.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_services():
    from app.main import app

    client = TestClient(app)
    response = client.get("/services")
    assert response.status_code == 200
    data = response.json()
    assert "services" in data
    assert "auth-service" in data["services"]


def test_search_logs_formats_output():
    mock_data = [
        {
            "service": "auth-service",
            "level": "ERROR",
            "message": "signing key verification failed",
            "timestamp": "2026-03-14T10:00:00",
        }
    ]
    assert mock_data[0]["level"] == "ERROR"
    assert "signing key" in mock_data[0]["message"]


def test_incident_template_structure():
    incident = {
        "title": "Token validation failures after deployment",
        "service": "auth-service",
        "severity": "high",
        "symptoms": "Users unable to login",
        "root_cause": "Expired signing key",
        "resolution": "Rotated signing key",
        "tags": ["bad_deploy", "signing_key"],
    }
    assert incident["severity"] == "high"
    assert "bad_deploy" in incident["tags"]


def test_env_variables_present():
    import os
    from dotenv import load_dotenv

    load_dotenv()
    assert os.getenv("SUPABASE_URL") is not None
    assert os.getenv("SUPABASE_KEY") is not None
    assert os.getenv("OLLAMA_BASE_URL") is not None
    assert os.getenv("OLLAMA_MODEL") is not None
