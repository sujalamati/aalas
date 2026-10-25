from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User, Job
from app.schemas import SearchRequest, JobOut
from app.services.search import fetch_and_store, rank_jobs

router = APIRouter(tags=["jobs"])

@router.post("/users/{user_id}/search", response_model=list[JobOut])
async def search_jobs(user_id: int, payload: SearchRequest, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user: raise HTTPException(404, "User not found.")
    if payload.refresh:
        try:
            await fetch_and_store(db, user, payload.limit)
        except Exception as exc:
            # Existing cached results can still be returned; expose provider failure in response only
            # if there are no cached jobs.
            if not db.query(Job).filter_by(user_id=user_id).first():
                raise HTTPException(502, f"Job provider failed: {exc}")
    return await rank_jobs(db, user, payload.limit)

@router.get("/users/{user_id}/jobs", response_model=list[JobOut])
async def list_jobs(user_id: int, limit: int = 25, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user: raise HTTPException(404, "User not found.")
    return await rank_jobs(db, user, max(1, min(limit, 100)))

@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job: raise HTTPException(404, "Job not found.")
    return job
