from __future__ import annotations

import json
import os
import random
import time
from typing import Any, Dict

from job_queue import (
    rconn, move_due_retries_to_ready, update_status, get_job,
    schedule_retry, dead_letter, Q_READY,
)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# --- Demo job handlers ---
def handle(job_type: str, payload: Dict[str, Any]) -> None:
    """
    Simulate different job workloads.
    """
    if job_type == "email_send":
        time.sleep(1.0)
        # simulate occasional failure
        if random.random() < 0.25:
            raise RuntimeError("SMTP provider timeout")
    elif job_type == "pdf_render":
        time.sleep(2.0)
        if random.random() < 0.20:
            raise RuntimeError("PDF renderer crashed")
    elif job_type == "data_sync":
        time.sleep(1.5)
        if random.random() < 0.15:
            raise RuntimeError("Upstream API rate-limited")
    else:
        time.sleep(0.8)
        if random.random() < 0.10:
            raise RuntimeError("Unknown job intermittent failure")

def backoff_seconds(attempt: int) -> int:
    # exponential backoff: 2, 4, 8, capped
    return min(30, 2 ** max(1, attempt))

def main():
    r = rconn(REDIS_URL)
    print("Worker started. Redis:", r.ping())

    while True:
        # Move due retries into ready queue
        move_due_retries_to_ready(r)

        # Blocking pop: waits up to 2s for a job id
        item = r.blpop(Q_READY, timeout=2)
        if not item:
            continue

        _, job_id = item
        job = get_job(r, job_id)
        if not job:
            continue

        attempt = int(job.get("attempt", 0)) + 1
        max_retries = int(job.get("max_retries", 3))
        job_type = job.get("type", "unknown")
        payload = job.get("payload", {}) or {}

        update_status(r, job_id, "RUNNING", attempt=attempt)

        try:
            handle(job_type, payload)
            update_status(r, job_id, "SUCCEEDED", last_error="")
        except Exception as e:
            err = str(e)
            if attempt <= max_retries:
                update_status(r, job_id, "FAILED", last_error=err)
                delay = backoff_seconds(attempt)
                schedule_retry(r, job_id, delay_seconds=delay)
            else:
                update_status(r, job_id, "FAILED", last_error=err)
                dead_letter(r, job_id)

if __name__ == "__main__":
    main()
