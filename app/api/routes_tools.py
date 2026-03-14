from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.db.timeline import get_timeline, get_multi_service_timeline
from app.db.vector_store import get_pattern_summary
import os

router = APIRouter(prefix="/tools", tags=["tools"])

class TimelineRequest(BaseModel):
    services: list[str]
    hours: int = 48

class PatternRequest(BaseModel):
    query: str
    top_k: int = 3

@router.post("/timeline")
def timeline(req: TimelineRequest):
    try:
        events = get_multi_service_timeline(req.services, req.hours)
        return {"events": events, "count": len(events)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/patterns")
def patterns(req: PatternRequest):
    try:
        summary = get_pattern_summary(req.query)
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs/{service}")
def get_logs(service: str, limit: int = 20):
    from app.db.supabase_client import get_client
    sb = get_client()
    result = sb.table("logs").select("*").eq("service", service).order("timestamp", desc=True).limit(limit).execute()
    return {"logs": result.data, "count": len(result.data)}

@router.get("/deployments/{service}")
def get_deployments(service: str, limit: int = 5):
    from app.db.supabase_client import get_client
    sb = get_client()
    result = sb.table("deployments").select("*").eq("service", service).order("deployed_at", desc=True).limit(limit).execute()
    return {"deployments": result.data, "count": len(result.data)}

@router.get("/incidents/{service}")
def get_incidents(service: str, limit: int = 10):
    from app.db.supabase_client import get_client
    sb = get_client()
    result = sb.table("incidents").select("*").eq("service", service).order("start_time", desc=True).limit(limit).execute()
    return {"incidents": result.data, "count": len(result.data)}