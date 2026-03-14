import os
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
server = Server("opspilot-tools")


@server.list_tools()
async def list_tools():
    return [
        types.Tool(
            name="search_logs",
            description="Search recent logs for a service by keyword and severity level",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service name e.g. auth-service"},
                    "keyword": {
                        "type": "string",
                        "description": "Keyword to search in log messages",
                    },
                    "level": {
                        "type": "string",
                        "description": "Log level: ERROR, WARN, INFO",
                        "default": "ERROR",
                    },
                },
                "required": ["service"],
            },
        ),
        types.Tool(
            name="search_incidents",
            description="Search past incidents by service and symptom keywords",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service name"},
                    "query": {"type": "string", "description": "Symptom or keyword to search"},
                },
                "required": ["service"],
            },
        ),
        types.Tool(
            name="get_recent_deployments",
            description="Get recent deployments for a service",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service name"},
                    "limit": {
                        "type": "integer",
                        "description": "Number of deployments to return",
                        "default": 5,
                    },
                },
                "required": ["service"],
            },
        ),
        types.Tool(
            name="search_runbooks",
            description="Search runbook content for a service to find troubleshooting steps",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {"type": "string", "description": "Service name"},
                    "query": {"type": "string", "description": "What to look for in the runbook"},
                },
                "required": ["service"],
            },
        ),
        types.Tool(
            name="save_resolution",
            description="Save a resolved incident investigation for future reuse",
            inputSchema={
                "type": "object",
                "properties": {
                    "service": {"type": "string"},
                    "title": {"type": "string"},
                    "symptoms": {"type": "string"},
                    "root_cause": {"type": "string"},
                    "resolution": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["service", "title", "root_cause", "resolution"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "search_logs":
        query = sb.table("logs").select("*").eq("service", arguments["service"])
        if "level" in arguments:
            query = query.eq("level", arguments["level"])
        if "keyword" in arguments:
            query = query.ilike("message", f"%{arguments['keyword']}%")
        result = query.order("timestamp", desc=True).limit(10).execute()
        logs = result.data
        if not logs:
            return [
                types.TextContent(type="text", text=f"No logs found for {arguments['service']}")
            ]
        error_count = sum(1 for log in logs if log["level"] == "ERROR")
        summary = (
            f"Found {len(logs)} log entries for {arguments['service']} ({error_count} errors):\n\n"
        )
        for log in logs:
            summary += f"[{log['level']}] {log['timestamp'][:19]} — {log['message']}\n"
        return [types.TextContent(type="text", text=summary)]

    elif name == "search_incidents":
        query = sb.table("incidents").select("*").eq("service", arguments["service"])
        if "query" in arguments:
            kw = arguments["query"]
            query = query.or_(f"symptoms.ilike.%{kw}%,root_cause.ilike.%{kw}%,title.ilike.%{kw}%")
        result = query.order("start_time", desc=True).limit(5).execute()
        incidents = result.data
        if not incidents:
            return [
                types.TextContent(
                    type="text", text=f"No past incidents found for {arguments['service']}"
                )
            ]
        summary = f"Found {len(incidents)} past incidents for {arguments['service']}:\n\n"
        for inc in incidents:
            summary += f"[{inc['severity'].upper()}] {inc['title']}\n"
            summary += f"  Symptoms: {inc['symptoms']}\n"
            summary += f"  Root cause: {inc['root_cause']}\n"
            summary += f"  Resolution: {inc['resolution']}\n\n"
        return [types.TextContent(type="text", text=summary)]

    elif name == "get_recent_deployments":
        limit = arguments.get("limit", 5)
        result = (
            sb.table("deployments")
            .select("*")
            .eq("service", arguments["service"])
            .order("deployed_at", desc=True)
            .limit(limit)
            .execute()
        )
        deploys = result.data
        if not deploys:
            return [
                types.TextContent(
                    type="text", text=f"No deployments found for {arguments['service']}"
                )
            ]
        summary = f"Recent deployments for {arguments['service']}:\n\n"
        for d in deploys:
            summary += (
                f"  {d['version']} — deployed at {d['deployed_at'][:19]} by {d['changed_by']}\n"
            )
            summary += f"  Notes: {d['notes']}\n"
            summary += f"  Commit: {d['commit_sha']}\n\n"
        return [types.TextContent(type="text", text=summary)]

    elif name == "search_runbooks":
        result = (
            sb.table("services").select("runbook, name").eq("name", arguments["service"]).execute()
        )
        if not result.data:
            return [
                types.TextContent(type="text", text=f"No runbook found for {arguments['service']}")
            ]
        runbook = result.data[0]["runbook"]
        query = arguments.get("query", "").lower()
        if query:
            lines = runbook.split("\n")
            relevant = [line for line in lines if query in line.lower() or line.startswith("#")]
            runbook = "\n".join(relevant) if relevant else runbook
        return [
            types.TextContent(type="text", text=f"Runbook for {arguments['service']}:\n\n{runbook}")
        ]

    elif name == "save_resolution":
        record = {
            "service": arguments["service"],
            "title": arguments["title"],
            "symptoms": arguments.get("symptoms", ""),
            "root_cause": arguments["root_cause"],
            "resolution": arguments["resolution"],
            "tags": arguments.get("tags", []),
            "status": "resolved",
            "severity": "medium",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
        }
        result = sb.table("incidents").insert(record).execute()
        return [
            types.TextContent(type="text", text=f"Resolution saved with id: {result.data[0]['id']}")
        ]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    async with stdio_server() as streams:
        await server.run(*streams, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
