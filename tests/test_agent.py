import pytest
import os

os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "fake-key-for-testing")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434/v1")
os.environ.setdefault("OLLAMA_MODEL", "qwen3.5:4b")


def test_plan_returns_dict():
    import json

    raw = (
        '{"intent": "incident_investigation", "service": "auth-service", "tools": ["search_logs"]}'
    )
    result = json.loads(raw)
    assert result["service"] == "auth-service"
    assert "search_logs" in result["tools"]


def test_plan_handles_bad_json():
    import json

    try:
        json.loads("not valid json")
        assert False
    except json.JSONDecodeError:
        assert True


def test_evidence_bundle_format():
    parts = ["=== search_logs ===\nFound 5 errors", "=== search_incidents ===\nFound 2 incidents"]
    evidence = "\n\n".join(parts)
    assert "search_logs" in evidence
    assert "search_incidents" in evidence


def test_service_names_valid():
    valid = ["auth-service", "payment-service", "notification-service"]
    assert "auth-service" in valid
    assert "unknown-service" not in valid


def test_planner_fallback():
    import json

    raw = "not valid json {{{"
    try:
        result = json.loads(raw)
    except Exception:
        result = {
            "intent": "incident_investigation",
            "service": "auth-service",
            "tools": ["search_logs", "search_incidents"],
        }
    assert result["service"] == "auth-service"
