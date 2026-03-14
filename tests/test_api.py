import pytest
import os

os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "fake-key-for-testing")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("OLLAMA_MODEL", "qwen3.5:4b")

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def get_test_client():
    from app.main import app

    return TestClient(app)


def test_health():
    client = get_test_client()
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_services():
    client = get_test_client()
    r = client.get("/services")
    assert r.status_code == 200
    names = [s["name"] for s in r.json()["services"]]
    assert "auth-service" in names
    assert "payment-service" in names


def test_get_logs_endpoint():
    mock_data = [
        {
            "service": "auth-service",
            "level": "ERROR",
            "message": "signing key failed",
            "timestamp": "2026-03-14T10:00:00",
        }
    ]
    with patch("app.api.routes_tools.get_client") as mock_get:
        mock_sb = MagicMock()
        mock_get.return_value = mock_sb
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = (
            mock_data
        )
        client = get_test_client()
        r = client.get("/tools/logs/auth-service")
        assert r.status_code == 200
        assert r.json()["count"] == 1


def test_get_deployments_endpoint():
    mock_data = [
        {
            "service": "auth-service",
            "version": "v1.8.4",
            "deployed_at": "2026-03-14T10:00:00",
            "changed_by": "alice",
            "notes": "test",
            "commit_sha": "abc123",
        }
    ]
    with patch("app.api.routes_tools.get_client") as mock_get:
        mock_sb = MagicMock()
        mock_get.return_value = mock_sb
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = (
            mock_data
        )
        client = get_test_client()
        r = client.get("/tools/deployments/auth-service")
        assert r.status_code == 200
        assert r.json()["count"] == 1


def test_get_incidents_endpoint():
    mock_data = [
        {
            "service": "auth-service",
            "title": "Token failure",
            "severity": "high",
            "status": "resolved",
            "start_time": "2026-03-14T10:00:00",
            "end_time": "2026-03-14T11:00:00",
            "symptoms": "login failing",
            "root_cause": "key expired",
            "resolution": "rotated key",
            "tags": ["bad_deploy"],
        }
    ]
    with patch("app.api.routes_tools.get_client") as mock_get:
        mock_sb = MagicMock()
        mock_get.return_value = mock_sb
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = (
            mock_data
        )
        client = get_test_client()
        r = client.get("/tools/incidents/auth-service")
        assert r.status_code == 200
        assert r.json()["count"] == 1
