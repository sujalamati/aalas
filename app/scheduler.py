import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.orm import Session
from app.config import settings
from app.db import SessionLocal
from app.models import User
from app.services.search import fetch_and_store

log = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone=settings.timezone)

async def refresh_all_users():
    db: Session = SessionLocal()
    try:
        users = db.query(User).all()
        for user in users:
            try:
                await fetch_and_store(db, user, settings.job_search_limit)
            except Exception:
                log.exception("Scheduled job refresh failed for user_id=%s", user.id)
    finally:
        db.close()

def start_scheduler():
    if not settings.scheduler_enabled:
        return
    if not scheduler.running:
        # Noon and midnight in Asia/Kolkata by default. Configure SCHEDULER_ENABLED=false in tests.
        scheduler.add_job(refresh_all_users, "cron", hour="0,12", minute=0, id="job-refresh", replace_existing=True)
        scheduler.start()

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
