import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

def get_client():
    from app.main import app
    return TestClient(app)

def test_health():
    client = get_client()
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_list_services():
    client = get_client()
    r = client.get("/services")
    assert r.status_code == 200
    names = [s["name"] for s in r.json()["services"]]
    assert "auth-service" in names

def test_get_logs_endpoint():
    mock_data = [{"service": "auth-service", "level": "ERROR", "message": "test", "timestamp": "2026-03-14T10:00:00"}]
    with patch("app.api.routes_tools.get_client") as mock_sb:
        mock_sb.return_value.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = mock_data
        client = get_client()
        r = client.get("/tools/logs/auth-service")
        assert r.status_code == 200

def test_get_deployments_endpoint():
    mock_data = [{"service": "auth-service", "version": "v1.8.4", "deployed_at": "2026-03-14T10:00:00", "changed_by": "alice", "notes": "test", "commit_sha": "abc123"}]
    with patch("app.api.routes_tools.get_client") as mock_sb:
        mock_sb.return_value.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = mock_data
        client = get_client()
        r = client.get("/tools/deployments/auth-service")
        assert r.status_code == 200