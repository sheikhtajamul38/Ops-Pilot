from fastapi import FastAPI
from app.api.routes_query import router as query_router
from app.api.routes_tools import router as tools_router

app = FastAPI(
    title="OpsPilot API",
    version="1.0.0",
    description="Local AI ops copilot — incident investigation API",
)

app.include_router(query_router)
app.include_router(tools_router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/services")
def list_services():
    return {
        "services": [
            {"name": "auth-service", "owner": "platform-team"},
            {"name": "payment-service", "owner": "payments-team"},
            {"name": "notification-service", "owner": "comms-team"},
        ]
    }
