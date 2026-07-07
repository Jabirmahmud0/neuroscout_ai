"""NeuroScout AI - FastAPI backend.

Endpoints:
  GET  /api/health                - System health
  POST /api/research/stream       - SSE stream of agent steps + final report
  GET  /api/sessions              - List recent sessions (max 20)
  GET  /api/sessions/{id}         - Fetch full report for a session
  DELETE /api/sessions/{id}       - Delete a session
"""
from __future__ import annotations

import json
import logging
import os
import uuid
import uvicorn
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, AsyncGenerator, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# Import after env is loaded so API keys are available
from agent import get_cache_stats, run_research  # noqa: E402

# ----- Mongo (initialized in lifespan) ----- #
db_client: Optional[AsyncIOMotorClient] = None
db = None

metrics_state: Dict[str, Any] = {
    "runs_started": 0,
    "runs_completed": 0,
    "runs_failed": 0,
    "search_calls": 0,
    "search_cache_hits": 0,
    "fetch_calls": 0,
    "fetch_cache_hits": 0,
    "llm_calls": 0,
    "llm_stage_counts": {"plan": 0, "reason": 0, "synthesize": 0, "polish": 0, "repair": 0},
    "avg_run_duration_sec": 0.0,
    "avg_search_duration_ms": 0.0,
    "avg_llm_duration_ms": 0.0,
    "recent_run_durations_sec": [],
    "recent_search_durations_ms": [],
    "recent_llm_durations_ms": [],
    "recent_source_counts": [],
    "last_run_completed_at": None,
}


def _append_metric(name: str, value: float, limit: int = 100) -> None:
    bucket = metrics_state[name]
    bucket.append(value)
    if len(bucket) > limit:
        del bucket[0 : len(bucket) - limit]


def _record_agent_metric(event: str, payload: Dict[str, Any]) -> None:
    if event == "run_started":
        metrics_state["runs_started"] += 1
    elif event == "run_completed":
        metrics_state["runs_completed"] += 1
        metrics_state["last_run_completed_at"] = datetime.now(timezone.utc).isoformat()
        _append_metric("recent_run_durations_sec", float(payload.get("duration_sec", 0)))
        _append_metric("recent_source_counts", float(payload.get("source_count", 0)))
    elif event == "search_completed":
        metrics_state["search_calls"] += 1
        if payload.get("cache_hit"):
            metrics_state["search_cache_hits"] += 1
        _append_metric("recent_search_durations_ms", float(payload.get("duration_ms", 0)))
    elif event == "fetch_completed":
        metrics_state["fetch_calls"] += int(payload.get("fetched_count", 0))
        metrics_state["fetch_cache_hits"] += int(payload.get("cache_hits", 0))
    elif event == "llm_call":
        metrics_state["llm_calls"] += 1
        stage = str(payload.get("stage") or "")
        if stage in metrics_state["llm_stage_counts"]:
            metrics_state["llm_stage_counts"][stage] += 1
        _append_metric("recent_llm_durations_ms", float(payload.get("duration_ms", 0)))


def _recompute_metric_averages() -> None:
    metrics_state["avg_run_duration_sec"] = round(mean(metrics_state["recent_run_durations_sec"]), 2) if metrics_state["recent_run_durations_sec"] else 0.0
    metrics_state["avg_search_duration_ms"] = round(mean(metrics_state["recent_search_durations_ms"]), 2) if metrics_state["recent_search_durations_ms"] else 0.0
    metrics_state["avg_llm_duration_ms"] = round(mean(metrics_state["recent_llm_durations_ms"]), 2) if metrics_state["recent_llm_durations_ms"] else 0.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("neuroscout")

# ----- Lifespan ----- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_client, db
    # Startup logic - connect to MongoDB asynchronously
    logger.info("Starting NeuroScout API")
    mongo_url = os.environ["MONGO_URL"]
    db_client = AsyncIOMotorClient(
        mongo_url,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
    )
    db = db_client[os.environ["DB_NAME"]]
    logger.info("MongoDB client initialised")
    yield
    # Shutdown logic
    logger.info("Shutting down NeuroScout API")
    if db_client:
        db_client.close()

# ----- App ----- #
app = FastAPI(
    title="NeuroScout AI",
    description="Autonomous research agent backend",
    version="1.0.0",
    lifespan=lifespan
)

api_router = APIRouter(prefix="/api")

# ----- Schemas ----- #
class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    max_iterations: int = Field(default=5, ge=2, le=8)
    mode: str = Field(default="balanced", pattern="^(quick|balanced|deep)$")

class SessionSummary(BaseModel):
    session_id: str
    query: str
    mode: Optional[str] = None
    status: str
    created_at: str
    completed_at: Optional[str] = None

class SessionDetail(SessionSummary):
    report: Optional[dict] = None
    error_message: Optional[str] = None

# ----- Routes ----- #
@api_router.get("/health")
async def health():
    _recompute_metric_averages()
    return {
        "status": "ok",
        "llm_configured": bool(os.environ.get("GEMINI_API_KEY")),
        "metrics": {
            "runs_started": metrics_state["runs_started"],
            "runs_completed": metrics_state["runs_completed"],
            "runs_failed": metrics_state["runs_failed"],
            "avg_run_duration_sec": metrics_state["avg_run_duration_sec"],
        },
        "cache": get_cache_stats(),
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@api_router.get("/metrics")
async def metrics():
    _recompute_metric_averages()
    return {
        "runs": {
            "started": metrics_state["runs_started"],
            "completed": metrics_state["runs_completed"],
            "failed": metrics_state["runs_failed"],
            "avg_duration_sec": metrics_state["avg_run_duration_sec"],
            "last_completed_at": metrics_state["last_run_completed_at"],
        },
        "search": {
            "calls": metrics_state["search_calls"],
            "cache_hits": metrics_state["search_cache_hits"],
            "cache_hit_rate": round(
                metrics_state["search_cache_hits"] / metrics_state["search_calls"], 3
            )
            if metrics_state["search_calls"]
            else 0.0,
            "avg_duration_ms": metrics_state["avg_search_duration_ms"],
        },
        "fetch": {
            "calls": metrics_state["fetch_calls"],
            "cache_hits": metrics_state["fetch_cache_hits"],
            "cache_hit_rate": round(
                metrics_state["fetch_cache_hits"] / metrics_state["fetch_calls"], 3
            )
            if metrics_state["fetch_calls"]
            else 0.0,
        },
        "llm": {
            "calls": metrics_state["llm_calls"],
            "by_stage": metrics_state["llm_stage_counts"],
            "avg_duration_ms": metrics_state["avg_llm_duration_ms"],
        },
        "cache": get_cache_stats(),
        "recent": {
            "run_durations_sec": metrics_state["recent_run_durations_sec"][-10:],
            "source_counts": metrics_state["recent_source_counts"][-10:],
        },
        "ts": datetime.now(timezone.utc).isoformat(),
    }

def _sse_format(event: dict) -> str:
    """Format a JSON dict as a Server-Sent Event."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

@api_router.post("/research/stream")
async def research_stream(req: ResearchRequest):
    """Run the agent and stream step events via SSE."""
    session_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    if db is None:
        raise HTTPException(status_code=503, detail="Database not ready yet, please retry")

    await db.research_sessions.insert_one({
        "session_id": session_id,
        "query": req.query,
        "mode": req.mode,
        "status": "pending",
        "created_at": created_at,
        "completed_at": None,
        "report": None,
        "error_message": None,
    })

    async def event_gen() -> AsyncGenerator[bytes, None]:
        yield _sse_format({"type": "session", "session_id": session_id}).encode("utf-8")

        final_report: Optional[dict] = None
        error_msg: Optional[str] = None

        try:
            async for event in run_research(req.query, req.max_iterations, req.mode, observer=_record_agent_metric):
                if event.get("type") == "final":
                    final_report = event.get("report")
                elif event.get("type") == "error":
                    error_msg = event.get("message", "unknown error")
                yield _sse_format(event).encode("utf-8")
        except Exception as e:
            logging.exception("Agent loop crashed")
            error_msg = f"Agent crashed: {e}"
            yield _sse_format({"type": "error", "message": error_msg}).encode("utf-8")

        completed_at = datetime.now(timezone.utc).isoformat()
        update = {
            "completed_at": completed_at,
            "status": "completed" if final_report else "failed",
            "report": final_report,
            "error_message": error_msg,
        }
        if final_report is None:
            metrics_state["runs_failed"] += 1
        await db.research_sessions.update_one(
            {"session_id": session_id}, {"$set": update}
        )
        yield _sse_format({"type": "done", "session_id": session_id,
                           "status": update["status"]}).encode("utf-8")

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

@api_router.get("/sessions", response_model=List[SessionSummary])
async def list_sessions():
    try:
        cursor = db.research_sessions.find(
            {},
            {"_id": 0, "session_id": 1, "query": 1, "status": 1,
             "mode": 1, "created_at": 1, "completed_at": 1},
        ).sort("created_at", -1).limit(20)
        return [SessionSummary(**doc) async for doc in cursor]
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@api_router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str):
    doc = await db.research_sessions.find_one({"session_id": session_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionDetail(**doc)

@api_router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    res = await db.research_sessions.delete_one({"session_id": session_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"deleted": True}

app.include_router(api_router)

cors_origins_str = os.environ.get("CORS_ORIGINS", "")
_extra_origins = [o.strip() for o in cors_origins_str.split(",") if o.strip()] if cors_origins_str else []
origins = list({
    "http://localhost:3000",
    "https://neuroscout-ai.vercel.app",
    *_extra_origins,
})

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# (logging configured above lifespan)

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
