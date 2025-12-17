from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from job_queue import rconn, create_job, get_job, list_jobs, PUBSUB

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = FastAPI(title="Distributed Job System API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CreateJobRequest(BaseModel):
    type: str = Field(..., examples=["email_send", "pdf_render", "data_sync"])
    payload: Dict[str, Any] = Field(default_factory=dict)
    max_retries: int = 3

@app.get("/api/health")
def health():
    r = rconn(REDIS_URL)
    return {"ok": True, "redis": r.ping()}

@app.post("/api/jobs")
def api_create_job(body: CreateJobRequest):
    r = rconn(REDIS_URL)
    return create_job(r, body.type, body.payload, max_retries=body.max_retries)

@app.get("/api/jobs")
def api_list_jobs(limit: int = 50):
    r = rconn(REDIS_URL)
    return {"jobs": list_jobs(r, limit=limit)}

@app.get("/api/jobs/{job_id}")
def api_get_job(job_id: str):
    r = rconn(REDIS_URL)
    j = get_job(r, job_id)
    if not j:
        return {"error": "not_found"}
    return j

# ---- WebSocket for real-time updates ----
@app.websocket("/ws")
async def ws_events(ws: WebSocket):
    await ws.accept()
    r = rconn(REDIS_URL)
    pubsub = r.pubsub()
    pubsub.subscribe(PUBSUB)

    try:
        # Send initial “connected”
        await ws.send_text(json.dumps({"event": "CONNECTED"}))

        while True:
            # poll pubsub without blocking the event loop too hard
            msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg and msg.get("data"):
                await ws.send_text(msg["data"])
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            pubsub.unsubscribe(PUBSUB)
            pubsub.close()
        except Exception:
            pass
