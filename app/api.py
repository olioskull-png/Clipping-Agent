import json, os, shutil, threading, uuid, traceback
from typing import Any, Literal, Optional
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from app.jobs import JobState, JobStatus, get_job, list_jobs, set_job, update_job, utcnow
from app.pipeline import run_job
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
@app.get("/")
def serve_dashboard(): return FileResponse(os.path.join("static", "index.html"))
class JobCreate(BaseModel):
    url: str
    clips_count: int = Field(default=3, ge=1, le=10)
    min_duration: float = Field(default=15.0, ge=3, le=600)
    max_duration: float = Field(default=60.0, ge=5, le=900)
_semaphore = threading.Semaphore(1)
def _progress_callback(job_id: str, step: str, extra=None): update_job(job_id, current_step=step)
def _process_job(job_id: str, payload: JobCreate):
    with _semaphore:
        try:
            update_job(job_id, status=JobStatus.PROCESSING)
            metadata = run_job(payload.url, payload.clips_count, payload.min_duration, payload.max_duration, job_id, _progress_callback)
            update_job(job_id, status=JobStatus.COMPLETED, metadata=metadata)
        except Exception as e:
            update_job(job_id, status=JobStatus.FAILED, error=str(e))
            traceback.print_exc()
@app.post("/jobs", status_code=202)
def create_job(payload: JobCreate, background_tasks: BackgroundTasks):
    job_id = uuid.uuid4().hex[:12]
    job = JobState(job_id=job_id, status=JobStatus.QUEUED, created_at=utcnow(), updated_at=utcnow(), source_url=payload.url, clips_count=payload.clips_count, min_duration=payload.min_duration, max_duration=payload.max_duration)
    set_job(job)
    background_tasks.add_task(_process_job, job_id, payload)
    return get_job(job_id)


ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


@app.post("/jobs/upload", status_code=202)
def create_upload_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    clips_count: int = Form(default=3, ge=1, le=10),
    min_duration: float = Form(default=15.0, ge=3, le=600),
    max_duration: float = Form(default=60.0, ge=5, le=900),
):
    filename = os.path.basename(file.filename or "video.mp4")
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(400, f"Format video nesuportat ({ext}). Folosește: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}")

    job_id = uuid.uuid4().hex[:12]
    raw_dir = os.path.join("storage", "raw")
    os.makedirs(raw_dir, exist_ok=True)
    saved_path = os.path.join(raw_dir, f"local_{job_id}{ext}")

    with open(saved_path, "wb") as out_file:
        shutil.copyfileobj(file.file, out_file)

    job = JobState(
        job_id=job_id,
        status=JobStatus.QUEUED,
        created_at=utcnow(),
        updated_at=utcnow(),
        source_url=f"local://{filename}",
        clips_count=clips_count,
        min_duration=min_duration,
        max_duration=max_duration,
    )
    set_job(job)
    payload = JobCreate(url=saved_path, clips_count=clips_count, min_duration=min_duration, max_duration=max_duration)
    background_tasks.add_task(_process_job, job_id, payload)
    return get_job(job_id)
@app.get("/jobs")
def jobs(): return list_jobs()
@app.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = get_job(job_id)
    if not job: raise HTTPException(404, "Not found")
    return job
@app.get("/jobs/{job_id}/result")
def job_result(job_id: str):
    job = get_job(job_id)
    if not job: raise HTTPException(404, "Not found")
    if job.status != JobStatus.COMPLETED: return JSONResponse(409, {"status": job.status})
    return job.metadata
@app.get("/jobs/{job_id}/files/{filename}")
def job_file(job_id: str, filename: str):
    file_path = os.path.join("output", job_id, os.path.basename(filename))
    if not os.path.isfile(file_path): raise HTTPException(404, "File not found")
    return FileResponse(file_path)


class ClipReviewUpdate(BaseModel):
    review_status: Optional[Literal["pending_review", "approved", "rejected"]] = None
    title: Optional[str] = None
    social: Optional[dict[str, Any]] = None


@app.patch("/jobs/{job_id}/clips/{clip_id}")
def update_clip_review(job_id: str, clip_id: str, payload: ClipReviewUpdate):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if not job.metadata or "clips" not in job.metadata:
        raise HTTPException(404, "No clips metadata found for job")

    updated_clip = None
    metadata = dict(job.metadata)
    clips = list(metadata.get("clips", []))
    for idx, clip in enumerate(clips):
        if clip.get("clip_id") == clip_id:
            clip = dict(clip)
            if payload.review_status is not None:
                clip["review_status"] = payload.review_status
            if payload.title is not None:
                clip["title"] = payload.title
            if payload.social is not None:
                clip["social"] = payload.social
            clips[idx] = clip
            updated_clip = clip
            break

    if updated_clip is None:
        raise HTTPException(404, "Clip not found")

    metadata["clips"] = clips
    update_job(job_id, metadata=metadata)

    metadata_path = os.path.join("output", job_id, "metadata.json")
    if os.path.isdir(os.path.dirname(metadata_path)):
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    return updated_clip
