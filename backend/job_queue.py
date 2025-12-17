from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

import redis

# Redis keys
Q_READY = "jobs:ready"            # list (FIFO)
Q_RETRY = "jobs:retry"            # sorted set (score = next_run_epoch)
Q_DEAD  = "jobs:dead"             # list
HASH_JOB = "job:"                 # hash prefix
PUBSUB = "jobs:events"            # pub/sub channel

def now() -> int:
    return int(time.time())

def rconn(url: str) -> redis.Redis:
    return redis.Redis.from_url(url, decode_responses=True)

def job_key(job_id: str) -> str:
    return f"{HASH_JOB}{job_id}"

def publish(r: redis.Redis, event: Dict[str, Any]) -> None:
    r.publish(PUBSUB, json.dumps(event))

def create_job(
    r: redis.Redis,
    job_type: str,
    payload: Dict[str, Any],
    max_retries: int = 3,
) -> Dict[str, Any]:
    job_id = str(uuid.uuid4())[:8]
    created_at = now()
    doc = {
        "id": job_id,
        "type": job_type,
        "payload": json.dumps(payload),
        "status": "QUEUED",              # QUEUED | RUNNING | SUCCEEDED | FAILED | DEAD
        "created_at": created_at,
        "updated_at": created_at,
        "attempt": 0,
        "max_retries": max_retries,
        "last_error": "",
    }
    r.hset(job_key(job_id), mapping=doc)
    r.rpush(Q_READY, job_id)

    publish(r, {"event": "JOB_CREATED", "job_id": job_id, "type": job_type, "ts": created_at})
    return _job_to_dict(r, job_id)

def _job_to_dict(r: redis.Redis, job_id: str) -> Dict[str, Any]:
    h = r.hgetall(job_key(job_id))
    if not h:
        return {}
    out = dict(h)
    # decode payload
    try:
        out["payload"] = json.loads(out.get("payload") or "{}")
    except Exception:
        out["payload"] = {}
    # ints
    for k in ("created_at","updated_at","attempt","max_retries"):
        if k in out and out[k] != "":
            out[k] = int(out[k])
    return out

def get_job(r: redis.Redis, job_id: str) -> Dict[str, Any]:
    return _job_to_dict(r, job_id)

def list_jobs(r: redis.Redis, limit: int = 50) -> List[Dict[str, Any]]:
    # This scans keys job:*; fine for demo. For prod, index IDs.
    ids = []
    for key in r.scan_iter(match="job:*", count=200):
        ids.append(key.split("job:")[1])
        if len(ids) >= limit:
            break
    jobs = [get_job(r, jid) for jid in ids]
    jobs = [j for j in jobs if j]
    jobs.sort(key=lambda x: x.get("created_at", 0), reverse=True)
    return jobs[:limit]

def update_status(r: redis.Redis, job_id: str, status: str, **fields: Any) -> None:
    fields["status"] = status
    fields["updated_at"] = now()
    if "payload" in fields and isinstance(fields["payload"], dict):
        fields["payload"] = json.dumps(fields["payload"])
    r.hset(job_key(job_id), mapping=fields)

    event = {"event": "JOB_UPDATED", "job_id": job_id, "status": status, "ts": fields["updated_at"]}
    if "last_error" in fields:
        event["last_error"] = fields["last_error"]
    publish(r, event)

def schedule_retry(r: redis.Redis, job_id: str, delay_seconds: int) -> None:
    run_at = now() + delay_seconds
    r.zadd(Q_RETRY, {job_id: run_at})
    publish(r, {"event": "JOB_RETRY_SCHEDULED", "job_id": job_id, "run_at": run_at, "ts": now()})

def move_due_retries_to_ready(r: redis.Redis, max_batch: int = 50) -> int:
    t = now()
    due = r.zrangebyscore(Q_RETRY, min=0, max=t, start=0, num=max_batch)
    if not due:
        return 0
    pipe = r.pipeline()
    for job_id in due:
        pipe.zrem(Q_RETRY, job_id)
        pipe.rpush(Q_READY, job_id)
    pipe.execute()
    publish(r, {"event": "RETRIES_RELEASED", "count": len(due), "ts": now()})
    return len(due)

def dead_letter(r: redis.Redis, job_id: str) -> None:
    r.lpush(Q_DEAD, job_id)
    update_status(r, job_id, "DEAD")
    publish(r, {"event": "JOB_DEAD", "job_id": job_id, "ts": now()})
