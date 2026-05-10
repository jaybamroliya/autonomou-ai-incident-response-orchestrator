"""
Autonomous AI Incident Response Orchestrator
Fake Incident Service — Realistic failure simulation for demo purposes.
"""

import os
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────────────────────────
SERVICE_NAME = os.getenv("SERVICE_NAME", "payment-api")
FAILURE_PROBABILITY = float(os.getenv("FAILURE_PROBABILITY", "0.3"))
BASE_LATENCY_MS = int(os.getenv("LATENCY_MS", "50"))

app = FastAPI(
    title=f"{SERVICE_NAME} — Incident Simulation Service",
    description="Realistic service failure simulator for AI incident response demos.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────
#  In-memory state
# ─────────────────────────────────────────────────────────────────
_state = {
    "healthy": True,
    "incident_active": False,
    "incident_id": None,
    "failure_type": None,
    "started_at": None,
    "request_count": 0,
    "error_count": 0,
    "total_latency_ms": 0,
}

_log_buffer: list[dict] = []

FAILURE_SCENARIOS = [
    {
        "type": "database_connection_pool_exhausted",
        "message": "FATAL: connection pool exhausted — max_connections=100 exceeded",
        "component": "postgres-primary",
        "http_status": 503,
        "latency_spike_ms": 5000,
    },
    {
        "type": "memory_leak_oom",
        "message": "OutOfMemoryError: Java heap space — GC overhead limit exceeded",
        "component": "jvm-runtime",
        "http_status": 500,
        "latency_spike_ms": 3000,
    },
    {
        "type": "downstream_api_timeout",
        "message": "ReadTimeout: upstream stripe-api did not respond within 30s",
        "component": "stripe-client",
        "http_status": 504,
        "latency_spike_ms": 30000,
    },
    {
        "type": "disk_io_saturation",
        "message": "IOError: write failed — disk utilization at 99.8% on /data volume",
        "component": "storage-layer",
        "http_status": 507,
        "latency_spike_ms": 8000,
    },
    {
        "type": "certificate_expiry",
        "message": "SSLError: certificate expired 2 hours ago for api.payments.internal",
        "component": "tls-terminator",
        "http_status": 495,
        "latency_spike_ms": 200,
    },
    {
        "type": "rate_limit_cascade",
        "message": "RateLimitExceeded: 429 from downstream — backoff exhausted after 5 retries",
        "component": "http-client",
        "http_status": 429,
        "latency_spike_ms": 2000,
    },
]

LOG_TEMPLATES = {
    "info": [
        "Request processed successfully in {latency}ms — txn_id={txn}",
        "Health check passed — all dependencies reachable",
        "Cache hit ratio: {ratio}% — Redis latency {lat}ms",
        "Scheduled cleanup completed — removed {n} stale sessions",
        "Config refreshed from Consul — 12 keys updated",
    ],
    "warning": [
        "Slow query detected ({latency}ms) — SELECT on payments table — consider index on created_at",
        "Connection pool utilization at {pct}% — approaching threshold",
        "Retry attempt {n}/3 for downstream call to fraud-service",
        "Memory usage at {pct}% — GC pause {gc_ms}ms",
        "Circuit breaker HALF_OPEN — probing stripe-api",
    ],
    "error": [
        "EXCEPTION: {exc} — txn_id={txn} — retries_exhausted=true",
        "Database deadlock detected — rolled back txn={txn}",
        "Panic: nil pointer dereference in handler PaymentController.Process",
        "CRITICAL: failed to write audit log — compliance violation risk",
        "Connection refused: redis://cache:6379 — failover to replica",
    ],
    "critical": [
        "FATAL: {msg}",
        "SERVICE DEGRADED: error rate {pct}% exceeds SLA threshold of 1%",
        "ALERT: p99 latency {latency}ms exceeds 2000ms SLO",
        "INCIDENT DETECTED: {failure_type} — auto-remediation triggered",
    ],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_log(level: str, context: Optional[dict] = None) -> dict:
    ctx = context or {}
    templates = LOG_TEMPLATES.get(level, LOG_TEMPLATES["info"])
    msg = random.choice(templates).format(
        latency=random.randint(10, 9000),
        txn=uuid.uuid4().hex[:12],
        ratio=random.randint(60, 99),
        lat=random.randint(1, 15),
        n=random.randint(1, 1000),
        pct=random.randint(70, 99),
        gc_ms=random.randint(50, 800),
        exc=ctx.get("exc", "NullPointerException"),
        msg=ctx.get("msg", "unknown error"),
        failure_type=ctx.get("failure_type", "unknown"),
    )
    entry = {
        "timestamp": _now_iso(),
        "level": level.upper(),
        "service": SERVICE_NAME,
        "message": msg,
        "trace_id": uuid.uuid4().hex[:16],
        "span_id": uuid.uuid4().hex[:8],
    }
    _log_buffer.append(entry)
    if len(_log_buffer) > 500:
        _log_buffer.pop(0)
    return entry


# ─────────────────────────────────────────────────────────────────
#  Endpoints
# ─────────────────────────────────────────────────────────────────


@app.get("/health", summary="Service health check")
async def health_check():
    """
    Returns 200 when healthy, 503 when an active incident is detected.
    Kestra polls this endpoint every minute.
    """
    _state["request_count"] += 1

    if _state["incident_active"]:
        _state["error_count"] += 1
        scenario = next(
            (s for s in FAILURE_SCENARIOS if s["type"] == _state["failure_type"]),
            FAILURE_SCENARIOS[0],
        )
        _gen_log("critical", {"msg": scenario["message"], "failure_type": _state["failure_type"]})
        raise HTTPException(
            status_code=scenario["http_status"],
            detail={
                "status": "unhealthy",
                "service": SERVICE_NAME,
                "incident_id": _state["incident_id"],
                "failure_type": _state["failure_type"],
                "message": scenario["message"],
                "component": scenario["component"],
                "started_at": _state["started_at"],
                "timestamp": _now_iso(),
            },
        )

    # Randomly degrade based on FAILURE_PROBABILITY
    if random.random() < FAILURE_PROBABILITY:
        scenario = random.choice(FAILURE_SCENARIOS)
        _state["incident_active"] = True
        _state["incident_id"] = f"INC-{uuid.uuid4().hex[:8].upper()}"
        _state["failure_type"] = scenario["type"]
        _state["started_at"] = _now_iso()
        _state["healthy"] = False
        _gen_log("critical", {"msg": scenario["message"], "failure_type": scenario["type"]})
        raise HTTPException(
            status_code=scenario["http_status"],
            detail={
                "status": "unhealthy",
                "service": SERVICE_NAME,
                "incident_id": _state["incident_id"],
                "failure_type": scenario["type"],
                "message": scenario["message"],
                "component": scenario["component"],
                "started_at": _state["started_at"],
                "timestamp": _now_iso(),
            },
        )

    _gen_log("info")
    latency = BASE_LATENCY_MS + random.randint(0, 30)
    _state["total_latency_ms"] += latency

    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "uptime_seconds": int(time.time() - _startup_time),
        "latency_ms": latency,
        "timestamp": _now_iso(),
        "version": "2.14.3",
        "checks": {
            "database": "ok",
            "redis": "ok",
            "downstream_apis": "ok",
            "disk": "ok",
        },
    }


@app.post("/simulate-failure", summary="Manually trigger a failure scenario")
async def simulate_failure(failure_type: Optional[str] = None):
    """
    Manually trigger a named failure scenario for demo purposes.
    If failure_type is omitted, a random scenario is chosen.
    """
    if _state["incident_active"]:
        return {
            "message": "Incident already active",
            "incident_id": _state["incident_id"],
            "failure_type": _state["failure_type"],
        }

    if failure_type:
        scenario = next((s for s in FAILURE_SCENARIOS if s["type"] == failure_type), None)
        if not scenario:
            valid = [s["type"] for s in FAILURE_SCENARIOS]
            raise HTTPException(400, f"Unknown failure type. Valid: {valid}")
    else:
        scenario = random.choice(FAILURE_SCENARIOS)

    _state["incident_active"] = True
    _state["incident_id"] = f"INC-{uuid.uuid4().hex[:8].upper()}"
    _state["failure_type"] = scenario["type"]
    _state["started_at"] = _now_iso()
    _state["healthy"] = False

    for _ in range(5):
        _gen_log("error", {"exc": scenario["type"], "txn": uuid.uuid4().hex[:12]})
    _gen_log("critical", {"msg": scenario["message"], "failure_type": scenario["type"]})

    return {
        "message": "Failure scenario activated",
        "incident_id": _state["incident_id"],
        "failure_type": scenario["type"],
        "component": scenario["component"],
        "description": scenario["message"],
        "started_at": _state["started_at"],
    }


@app.post("/resolve-incident", summary="Clear active incident (simulate recovery)")
async def resolve_incident():
    """Marks the current incident as resolved, restoring healthy state."""
    if not _state["incident_active"]:
        return {"message": "No active incident"}

    incident_id = _state["incident_id"]
    _state["incident_active"] = False
    _state["incident_id"] = None
    _state["failure_type"] = None
    _state["started_at"] = None
    _state["healthy"] = True
    _gen_log("info")

    return {
        "message": "Incident resolved",
        "incident_id": incident_id,
        "resolved_at": _now_iso(),
    }


@app.get("/logs", summary="Fetch recent service logs")
async def get_logs(limit: int = 50, level: Optional[str] = None):
    """
    Returns recent log entries. Kestra log-collection flow calls this.
    Use ?level=ERROR to filter by severity.
    """
    logs = list(reversed(_log_buffer))
    if level:
        logs = [l for l in logs if l["level"] == level.upper()]
    logs = logs[:limit]

    # Pad with synthetic logs if buffer is sparse
    if len(logs) < 10:
        for _ in range(20 - len(logs)):
            lvl = random.choices(
                ["info", "warning", "error", "critical"],
                weights=[60, 25, 12, 3],
            )[0]
            _gen_log(lvl)
        logs = list(reversed(_log_buffer))[:limit]

    return {
        "service": SERVICE_NAME,
        "total": len(logs),
        "incident_active": _state["incident_active"],
        "incident_id": _state["incident_id"],
        "logs": logs,
        "fetched_at": _now_iso(),
    }


@app.get("/metrics", summary="Service metrics snapshot")
async def get_metrics():
    """
    Returns Prometheus-style metrics as JSON.
    Used by Kestra for context in AI analysis.
    """
    req = _state["request_count"] or 1
    error_rate = round((_state["error_count"] / req) * 100, 2)
    avg_latency = round(_state["total_latency_ms"] / req, 1)

    return {
        "service": SERVICE_NAME,
        "timestamp": _now_iso(),
        "uptime_seconds": int(time.time() - _startup_time),
        "request_count": _state["request_count"],
        "error_count": _state["error_count"],
        "error_rate_pct": error_rate,
        "avg_latency_ms": avg_latency,
        "p99_latency_ms": avg_latency * random.uniform(3.0, 8.0) if _state["incident_active"] else avg_latency * random.uniform(1.1, 1.8),
        "active_connections": random.randint(10, 200),
        "memory_usage_mb": random.randint(256, 1800) if _state["incident_active"] else random.randint(256, 600),
        "cpu_usage_pct": random.uniform(60, 98) if _state["incident_active"] else random.uniform(5, 40),
        "gc_pause_ms": random.randint(200, 2000) if _state["incident_active"] else random.randint(5, 80),
        "db_pool_active": random.randint(80, 100) if _state["incident_active"] else random.randint(5, 40),
        "db_pool_max": 100,
        "cache_hit_rate_pct": random.uniform(10, 40) if _state["incident_active"] else random.uniform(75, 95),
        "incident_active": _state["incident_active"],
        "incident_id": _state["incident_id"],
        "failure_type": _state["failure_type"],
    }


@app.get("/status", summary="Full service status summary")
async def get_status():
    """Full status — combines health, metrics, and recent error logs."""
    error_logs = [l for l in reversed(_log_buffer) if l["level"] in ("ERROR", "CRITICAL")][:10]
    return {
        "service": SERVICE_NAME,
        "state": _state.copy(),
        "recent_errors": error_logs,
        "available_failure_scenarios": [s["type"] for s in FAILURE_SCENARIOS],
        "timestamp": _now_iso(),
    }


@app.get("/", summary="API root")
async def root():
    return {
        "service": SERVICE_NAME,
        "description": "AI Incident Response — Simulation Service",
        "endpoints": ["/health", "/metrics", "/logs", "/status", "/simulate-failure", "/resolve-incident"],
        "docs": "/docs",
    }


_startup_time = time.time()
