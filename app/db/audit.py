from app.db.supabase_client import get_client
from datetime import datetime, timezone

async def save_audit_log(query: str, service: str, tools_used: list, answer: str):
    try:
        sb = get_client()
        sb.table("audit_log").insert({
            "query": query,
            "service": service,
            "tools_used": tools_used,
            "answer": answer[:500],
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
    except Exception:
        pass