import json, os, sqlite3, threading
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
DB_PATH = os.getenv("DB_PATH", os.path.join("data", "jobs.db"))
_lock = threading.RLock()
class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
class JobState(BaseModel):
    job_id: str
    status: JobStatus
    created_at: str
    updated_at: str
    source_url: str
    clips_count: int
    min_duration: float
    max_duration: float
    current_step: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
def utcnow() -> str: return datetime.now(timezone.utc).isoformat()
def _ensure_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, status TEXT, created_at TEXT, updated_at TEXT, source_url TEXT, clips_count INTEGER, min_duration REAL, max_duration REAL, current_step TEXT, error TEXT, metadata TEXT)")
    conn.commit(); conn.close()
def _connect():
    _ensure_db()
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn
def _row_to_job(row):
    metadata = json.loads(row["metadata"]) if row["metadata"] else None
    return JobState(job_id=row["job_id"], status=JobStatus(row["status"]), created_at=row["created_at"], updated_at=row["updated_at"], source_url=row["source_url"], clips_count=row["clips_count"], min_duration=row["min_duration"], max_duration=row["max_duration"], current_step=row["current_step"], error=row["error"], metadata=metadata)
def set_job(job: JobState):
    with _lock:
        conn = _connect()
        conn.execute("INSERT OR REPLACE INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (job.job_id, job.status.value, job.created_at, job.updated_at, job.source_url, job.clips_count, job.min_duration, job.max_duration, job.current_step, job.error, json.dumps(job.metadata) if job.metadata else None))
        conn.commit(); conn.close()
def get_job(job_id: str):
    with _lock:
        conn = _connect()
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        conn.close()
        return _row_to_job(row) if row else None
def update_job(job_id: str, **kwargs):
    with _lock:
        job = get_job(job_id)
        if not job: return None
        data = job.model_dump()
        data.update(kwargs)
        data["updated_at"] = utcnow()
        new_job = JobState(**data)
        set_job(new_job)
        return new_job
def list_jobs(limit: int = 50):
    with _lock:
        conn = _connect()
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        conn.close()
        return [_row_to_job(r) for r in rows]
