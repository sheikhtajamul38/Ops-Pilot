from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.agent.agent import run_investigation, run_multi_service_investigation
from app.db.audit import save_audit_log
import os

router = APIRouter(prefix="/query", tags=["query"])


class QueryRequest(BaseModel):
    query: str
    mode: str = "single"


class QueryResponse(BaseModel):
    service: str | list
    tools_used: list
    answer: str
    evidence: str


@router.post("", response_model=QueryResponse)
async def query(req: QueryRequest):
    try:
        if req.mode == "multi":
            result = await run_multi_service_investigation(req.query)
            result["service"] = result.get("services", [])
        else:
            result = await run_investigation(req.query)

        await save_audit_log(
            query=req.query,
            service=result.get("service") or str(result.get("services", [])),
            tools_used=result.get("tools_used", []),
            answer=result.get("answer", ""),
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
