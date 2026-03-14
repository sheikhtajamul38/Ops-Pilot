import os
from dotenv import load_dotenv
from app.db.supabase_client import get_client
from datetime import datetime, timedelta, timezone

load_dotenv()


def get_timeline(service: str, hours: int = 48) -> list:
    sb = get_client()
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    events = []

    logs = (
        sb.table("logs")
        .select("*")
        .eq("service", service)
        .gte("timestamp", since)
        .order("timestamp", desc=False)
        .execute()
    )
    for log in logs.data:
        events.append(
            {
                "time": log["timestamp"],
                "type": "log",
                "level": log["level"],
                "message": log["message"],
                "service": service,
            }
        )

    deploys = (
        sb.table("deployments")
        .select("*")
        .eq("service", service)
        .gte("deployed_at", since)
        .order("deployed_at", desc=False)
        .execute()
    )
    for d in deploys.data:
        events.append(
            {
                "time": d["deployed_at"],
                "type": "deployment",
                "level": "INFO",
                "message": f"Deployed {d['version']} by {d['changed_by']} — {d['notes']}",
                "service": service,
            }
        )

    incidents = (
        sb.table("incidents")
        .select("*")
        .eq("service", service)
        .gte("start_time", since)
        .order("start_time", desc=False)
        .execute()
    )
    for inc in incidents.data:
        events.append(
            {
                "time": inc["start_time"],
                "type": "incident",
                "level": inc["severity"].upper(),
                "message": f"Incident: {inc['title']}",
                "service": service,
            }
        )

    events.sort(key=lambda x: x["time"])
    return events


def get_multi_service_timeline(services: list, hours: int = 48) -> list:
    all_events = []
    for svc in services:
        all_events.extend(get_timeline(svc, hours))
    all_events.sort(key=lambda x: x["time"])
    return all_events
