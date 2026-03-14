import os
import json
import asyncio
from openai import OpenAI
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.db.vector_store import get_pattern_summary
from app.db.timeline import get_timeline, get_multi_service_timeline
load_dotenv()

client = OpenAI(
    base_url=os.getenv("OLLAMA_BASE_URL"),
    api_key="ollama"
)
MODEL = os.getenv("OLLAMA_MODEL")
SERVER_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "tools", "mcp_server.py")

PLANNER_PROMPT = """You are an ops incident planner.
Given a user query, return ONLY valid JSON with this structure:
{
  "intent": "incident_investigation",
  "service": "<service name>",
  "tools": ["tool1", "tool2"]
}

Available tools: search_logs, search_incidents, get_recent_deployments, search_runbooks, save_resolution
Available services: auth-service, payment-service, notification-service

Return only JSON, no explanation."""

ANSWERER_PROMPT = """You are an incident investigation assistant for ops engineers.
You will be given evidence gathered from logs, incidents, deployments and runbooks.
Answer ONLY from the evidence provided.
Be concise and practical.
Always include:
- Likely root cause
- Supporting evidence
- Recommended next actions
- Confidence level (low/medium/high)
If evidence is missing or unclear, say so."""

async def plan(query: str) -> dict:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": PLANNER_PROMPT},
            {"role": "user", "content": query}
        ],
        temperature=0.1
    )
    raw = response.choices[0].message.content.strip()
    try:
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        return {
            "intent": "incident_investigation",
            "service": "auth-service",
            "tools": ["search_logs", "search_incidents", "get_recent_deployments"]
        }

async def run_investigation(query: str, status_callback=None) -> dict:
    def log(msg):
        if status_callback:
            status_callback(msg)
        else:
            print(msg)

    log("Planning investigation...")
    plan_result = await plan(query)
    service = plan_result.get("service", "auth-service")
    tools_to_run = plan_result.get("tools", ["search_logs", "search_incidents"])
    log(f"Service: {service} | Tools: {', '.join(tools_to_run)}")

    server_params = StdioServerParameters(
        command="python",
        args=[SERVER_SCRIPT]
    )

    evidence_parts = []

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            for tool_name in tools_to_run:
                if tool_name == "save_resolution":
                    continue
                log(f"Running tool: {tool_name}...")
                try:
                    args = {"service": service}
                    if tool_name == "search_logs":
                        args["level"] = "ERROR"
                    elif tool_name == "search_incidents":
                        args["query"] = query
                    elif tool_name == "get_recent_deployments":
                        args["limit"] = 5
                    elif tool_name == "search_runbooks":
                        args["query"] = query

                    result = await session.call_tool(tool_name, args)
                    evidence_parts.append(f"=== {tool_name} ===\n{result.content[0].text}")
                except Exception as e:
                    evidence_parts.append(f"=== {tool_name} ===\nError: {str(e)}")

    evidence = "\n\n".join(evidence_parts)
    log("Generating answer from evidence...")

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": ANSWERER_PROMPT},
            {"role": "user", "content": f"Query: {query}\n\nEvidence:\n{evidence}"}
        ],
        temperature=0.2
    )

    answer = response.choices[0].message.content.strip()
    return {
        "service": service,
        "tools_used": tools_to_run,
        "evidence": evidence,
        "answer": answer
    }

async def save_resolution(service: str, title: str, symptoms: str, root_cause: str, resolution: str, tags: list) -> str:
    server_params = StdioServerParameters(
        command="python",
        args=[SERVER_SCRIPT]
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("save_resolution", {
                "service": service,
                "title": title,
                "symptoms": symptoms,
                "root_cause": root_cause,
                "resolution": resolution,
                "tags": tags
            })
            return result.content[0].text

def draft_status_update(query: str, answer: str, service: str, channel: str = "slack") -> str:
    if channel == "slack":
        prompt = f"""Draft a concise Slack incident status update based on this investigation.
Use this format exactly:
:red_circle: *Incident Update — {service}*
*What happened:* one sentence
*Current status:* one sentence  
*Impact:* one sentence
*Next steps:* 2-3 bullet points
*Investigating team:* ops-team

Keep it under 150 words. Be factual and calm."""
    else:
        prompt = f"""Draft a professional email incident update based on this investigation.
Use this format:
Subject: [Incident Update] {service} — <short title>

Body:
- What happened (2 sentences)
- Current status (1 sentence)
- Impact on users (1 sentence)
- Next steps (2-3 bullet points)
- ETA for resolution if known

Keep it professional and under 200 words."""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Investigation query: {query}\n\nFindings:\n{answer}"}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

async def run_multi_service_investigation(query: str, status_callback=None) -> dict:
    def log(msg):
        if status_callback:
            status_callback(msg)
        else:
            print(msg)

    log("Detecting affected services...")
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": """You are an ops planner. Return ONLY valid JSON like:
{"services": ["auth-service", "payment-service"]}
Pick 1-3 from: auth-service, payment-service, notification-service"""},
            {"role": "user", "content": query}
        ],
        temperature=0.1
    )
    raw = response.choices[0].message.content.strip()
    try:
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        services = json.loads(raw.strip()).get("services", ["auth-service"])
    except Exception:
        services = ["auth-service"]

    log(f"Investigating services: {', '.join(services)}")

    all_evidence = []
    server_params = StdioServerParameters(command="python", args=[SERVER_SCRIPT])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for svc in services:
                log(f"Checking {svc}...")
                for tool_name in ["search_logs", "search_incidents", "get_recent_deployments"]:
                    try:
                        args = {"service": svc}
                        if tool_name == "search_incidents":
                            args["query"] = query
                        result = await session.call_tool(tool_name, args)
                        all_evidence.append(f"=== {tool_name} ({svc}) ===\n{result.content[0].text}")
                    except Exception as e:
                        all_evidence.append(f"=== {tool_name} ({svc}) ===\nError: {e}")

    log("Checking pattern history...")
    pattern = get_pattern_summary(query)
    all_evidence.append(f"=== pattern_matching ===\n{pattern}")

    evidence = "\n\n".join(all_evidence)
    log("Generating cross-service analysis...")

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": ANSWERER_PROMPT + "\nAlso identify if multiple services are related to the same root cause."},
            {"role": "user", "content": f"Query: {query}\n\nEvidence:\n{evidence}"}
        ],
        temperature=0.2
    )

    return {
        "services": services,
        "tools_used": ["search_logs", "search_incidents", "get_recent_deployments", "pattern_matching"],
        "evidence": evidence,
        "answer": response.choices[0].message.content.strip()
    }

    
if __name__ == "__main__":
    query = "Why is auth-service failing after the last deployment?"
    result = asyncio.run(run_investigation(query))
    print("\n" + "="*60)
    print("ANSWER:")
    print("="*60)
    print(result["answer"])