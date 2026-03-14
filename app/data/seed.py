import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

services = [
    {
        "name": "auth-service",
        "owner": "platform-team",
        "repo_url": "github.com/internal/auth-service",
        "runbook": """# auth-service runbook
Common failures:
- Redis latency spike
- Expired signing key
- Upstream profile service timeout
- Token validation errors after deployment

Checks:
1. Verify latest deployment time
2. Check Redis latency metrics
3. Confirm signing key freshness
4. Review token validation error rate
5. Check upstream profile service health

Resolution patterns:
- Redis latency: restart Redis, check memory usage
- Signing key: rotate key, redeploy auth-service
- Profile timeout: check profile-service health, increase timeout config
""",
        "dependencies": ["redis", "profile-service", "postgres"],
    },
    {
        "name": "payment-service",
        "owner": "payments-team",
        "repo_url": "github.com/internal/payment-service",
        "runbook": """# payment-service runbook
Common failures:
- DB connection pool exhaustion
- Stripe API timeout
- Kafka consumer lag
- Memory spike under load

Checks:
1. Check DB connection pool usage
2. Review recent deployments
3. Check Kafka consumer lag
4. Monitor memory usage trend
5. Verify Stripe API health

Resolution patterns:
- Pool exhaustion: increase max_connections, restart workers
- Stripe timeout: check Stripe status page, enable retry logic
- Kafka lag: scale consumers, check partition assignment
""",
        "dependencies": ["postgres", "kafka", "stripe-api", "redis"],
    },
    {
        "name": "notification-service",
        "owner": "comms-team",
        "repo_url": "github.com/internal/notification-service",
        "runbook": """# notification-service runbook
Common failures:
- Email provider rate limit
- SMS gateway timeout
- Queue backlog spike
- Template rendering error

Checks:
1. Check email provider rate limit status
2. Review SMS gateway response times
3. Monitor queue depth
4. Check template version after deployments

Resolution patterns:
- Rate limit: throttle send rate, switch to secondary provider
- SMS timeout: failover to backup gateway
- Queue backlog: scale workers, check for poison messages
""",
        "dependencies": ["rabbitmq", "sendgrid", "twilio", "postgres"],
    },
]

incident_templates = [
    {
        "title": "Token validation failures after deployment",
        "service": "auth-service",
        "severity": "high",
        "symptoms": "Users unable to login, token validation errors in logs, 401 responses spiking",
        "root_cause": "Expired signing key introduced during deployment rotation",
        "resolution": "Rotated signing key, redeployed auth-service, cleared token cache",
        "tags": ["bad_deploy", "signing_key", "auth_failure"],
    },
    {
        "title": "Redis latency causing auth timeouts",
        "service": "auth-service",
        "severity": "medium",
        "symptoms": "Slow login response times, Redis latency above 200ms, timeout errors",
        "root_cause": "Redis memory pressure due to missing TTL on session keys",
        "resolution": "Added TTL to session keys, flushed expired entries, restarted Redis",
        "tags": ["redis", "latency", "memory_pressure"],
    },
    {
        "title": "DB connection pool exhaustion",
        "service": "payment-service",
        "severity": "critical",
        "symptoms": "Payment requests timing out, connection pool errors, 503 responses",
        "root_cause": "New deployment increased connection count beyond pool limit",
        "resolution": "Increased max_connections to 100, restarted workers, rolled back config",
        "tags": ["db_timeout", "bad_deploy", "connection_pool"],
    },
    {
        "title": "Kafka consumer lag spike",
        "service": "payment-service",
        "severity": "medium",
        "symptoms": "Payment notifications delayed, Kafka lag above 50k messages",
        "root_cause": "Consumer group rebalance after pod restart caused processing slowdown",
        "resolution": "Scaled consumers to 6 replicas, rebalanced partitions",
        "tags": ["kafka_lag", "consumer_group", "scaling"],
    },
    {
        "title": "Email rate limit exceeded",
        "service": "notification-service",
        "severity": "medium",
        "symptoms": "Emails queued but not sent, SendGrid 429 errors, queue depth growing",
        "root_cause": "Marketing campaign triggered 10x normal email volume without rate limiting",
        "resolution": "Throttled send rate to 100/min, switched overflow to secondary provider",
        "tags": ["rate_limit", "email", "sendgrid"],
    },
    {
        "title": "Upstream profile service timeout",
        "service": "auth-service",
        "severity": "high",
        "symptoms": "Login requests failing for 30% of users, profile fetch timeout errors",
        "root_cause": "Profile service overloaded due to missing cache layer after cache flush",
        "resolution": "Re-enabled Redis cache for profile service, increased timeout to 5s",
        "tags": ["dependency_failure", "timeout", "cache"],
    },
    {
        "title": "Memory spike causing OOM restarts",
        "service": "payment-service",
        "severity": "critical",
        "symptoms": "Payment pods restarting, OOMKilled events, transaction failures",
        "root_cause": "Memory leak in payment reconciliation job introduced in v2.1.0",
        "resolution": "Rolled back to v2.0.9, patched reconciliation job memory handling",
        "tags": ["memory_pressure", "oom", "bad_deploy"],
    },
    {
        "title": "SMS gateway timeout",
        "service": "notification-service",
        "severity": "low",
        "symptoms": "SMS notifications delayed by 15 minutes, Twilio timeout errors",
        "root_cause": "Twilio regional outage affecting EU endpoints",
        "resolution": "Rerouted SMS traffic to US endpoint, delays cleared within 20 minutes",
        "tags": ["sms", "dependency_failure", "twilio"],
    },
]

deployment_templates = [
    {"version": "v1.8.4", "notes": "Updated signing key rotation logic"},
    {"version": "v1.8.3", "notes": "Performance improvements to token validation"},
    {"version": "v1.8.2", "notes": "Redis connection pool tuning"},
    {"version": "v2.1.0", "notes": "New payment reconciliation job"},
    {"version": "v2.0.9", "notes": "Kafka consumer scaling improvements"},
    {"version": "v2.0.8", "notes": "DB connection pool config update"},
    {"version": "v3.2.1", "notes": "Email template engine upgrade"},
    {"version": "v3.2.0", "notes": "SMS gateway failover logic added"},
    {"version": "v3.1.9", "notes": "Queue depth monitoring improvements"},
]

log_templates = [
    ("auth-service", "ERROR", "token validation failed for tenant={tenant}"),
    ("auth-service", "WARN", "redis latency exceeded threshold: {ms}ms"),
    ("auth-service", "ERROR", "upstream timeout calling user-profile service"),
    ("auth-service", "ERROR", "signing key verification failed"),
    ("auth-service", "INFO", "user login successful for tenant={tenant}"),
    ("payment-service", "ERROR", "connection pool exhausted: max_connections={n} reached"),
    ("payment-service", "ERROR", "stripe API timeout after {ms}ms"),
    ("payment-service", "WARN", "kafka consumer lag: {n} messages behind"),
    ("payment-service", "ERROR", "OOMKilled: memory limit exceeded"),
    ("payment-service", "INFO", "payment processed successfully: txn={txn}"),
    ("notification-service", "ERROR", "sendgrid rate limit exceeded: 429 response"),
    ("notification-service", "WARN", "queue depth growing: {n} messages pending"),
    ("notification-service", "ERROR", "twilio SMS gateway timeout after {ms}ms"),
    ("notification-service", "INFO", "email sent successfully to {n} recipients"),
]


def random_time(days_back=30):
    return (
        datetime.utcnow()
        - timedelta(
            days=random.randint(0, days_back),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
        )
    ).isoformat()


print("Seeding services...")
sb.table("services").delete().neq("id", 0).execute()
sb.table("services").insert(services).execute()

print("Seeding incidents...")
sb.table("incidents").delete().neq("id", 0).execute()
incidents = []
for tmpl in incident_templates:
    for _ in range(random.randint(2, 4)):
        start = datetime.utcnow() - timedelta(days=random.randint(1, 30))
        incidents.append(
            {
                **tmpl,
                "start_time": start.isoformat(),
                "end_time": (start + timedelta(hours=random.randint(1, 6))).isoformat(),
                "status": "resolved",
            }
        )
sb.table("incidents").insert(incidents).execute()

print("Seeding deployments...")
sb.table("deployments").delete().neq("id", 0).execute()
deployments = []
service_names = ["auth-service", "payment-service", "notification-service"]
engineers = ["alice", "bob", "carlos", "diana", "eve"]
for svc in service_names:
    for tmpl in random.sample(deployment_templates, 5):
        deployments.append(
            {
                "service": svc,
                "version": tmpl["version"],
                "deployed_at": random_time(14),
                "commit_sha": f"{random.randint(10000,99999):x}abc{random.randint(100,999)}",
                "changed_by": random.choice(engineers),
                "notes": tmpl["notes"],
            }
        )
sb.table("deployments").insert(deployments).execute()

print("Seeding logs...")
sb.table("logs").delete().neq("id", 0).execute()
logs = []
tenants = ["acme", "globex", "initech", "umbrella"]
for _ in range(200):
    tmpl = random.choice(log_templates)
    msg = tmpl[2].format(
        tenant=random.choice(tenants),
        ms=random.randint(100, 5000),
        n=random.randint(10, 100000),
        txn=f"txn_{random.randint(10000,99999)}",
    )
    logs.append({"service": tmpl[0], "level": tmpl[1], "message": msg, "timestamp": random_time(2)})
sb.table("logs").insert(logs).execute()

print("Done! All data seeded successfully.")
