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
from typing import AsyncGenerator, List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# Import after env is loaded so API keys are available
from agent import run_research  # noqa: E402

# ----- Mongo ----- #
mongo_url = os.environ["MONGO_URL"]
db_client = AsyncIOMotorClient(
    mongo_url,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000
)
db = db_client[os.environ["DB_NAME"]]

# ----- Lifespan ----- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Starting NeuroScout API")
    yield
    # Shutdown logic
    logger.info("Shutting down NeuroScout API")
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
    max_iterations: int = Field(default=5, ge=3, le=8)

class SessionSummary(BaseModel):
    session_id: str
    query: str
    status: str
    created_at: str
    completed_at: Optional[str] = None

class SessionDetail(SessionSummary):
    report: Optional[dict] = None
    error_message: Optional[str] = None

# ----- Routes ----- #
@api_router.get("/health")
async def health():
    return {
        "status": "ok",
        "llm_configured": bool(os.environ.get("GEMINI_API_KEY")),
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

    await db.research_sessions.insert_one({
        "session_id": session_id,
        "query": req.query,
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
            async for event in run_research(req.query, req.max_iterations):
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
             "created_at": 1, "completed_at": 1},
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

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("neuroscout")

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
