import re, os, shutil, subprocess, uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.models import User, Job
from app.schemas import TailorRequest, CoverLetterRequest
from app.services.llm import generate
from app.services.prompts import RESUME_SYSTEM, RESUME_USER_TEMPLATE, COVER_SYSTEM, COVER_USER_TEMPLATE

router = APIRouter(tags=["application documents"])
OUT = Path(settings.generated_dir).resolve()
OUT.mkdir(parents=True, exist_ok=True)

def _get_pair(db: Session, user_id: int, job_id: int):
    user, job = db.get(User, user_id), db.get(Job, job_id)
    if not user: raise HTTPException(404, "User not found.")
    if not job: raise HTTPException(404, "Job not found.")
    if job.user_id != user.id: raise HTTPException(403, "This job does not belong to this user's saved jobs.")
    if not user.resume_latex.strip(): raise HTTPException(400, "Upload or paste a LaTeX resume in the profile first.")
    return user, job

def _compile_latex(source: str, basename: str) -> Path:
    # Conservative check to reduce accidental unsafe compiler directives. This is not a full sandbox.
    if re.search(r"\\\\(write18|immediate\\s*\\\\write18|openout|read|input\\s*\\{\\s*/)", source, re.I):
        raise HTTPException(400, "Resume contains a prohibited LaTeX command.")
    tex_path = OUT / f"{basename}.tex"
    tex_path.write_text(source, encoding="utf-8")
    engine = settings.latex_engine
    if engine == "tectonic":
        command = ["tectonic", "--outdir", str(OUT), str(tex_path)]
    else:
        command = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-output-directory", str(OUT), str(tex_path)]
    try:
        result = subprocess.run(command, cwd=OUT, capture_output=True, text=True, timeout=90, check=False)
    except FileNotFoundError:
        raise HTTPException(503, f"LaTeX engine '{engine}' is not installed in the backend container.")
    if result.returncode != 0:
        raise HTTPException(422, "Generated LaTeX did not compile. Try again or inspect server logs.")
    pdf = OUT / f"{basename}.pdf"
    if not pdf.exists(): raise HTTPException(500, "LaTeX engine completed but no PDF was created.")
    return pdf

@router.post("/documents/tailor-resume")
async def tailor_resume(payload: TailorRequest, db: Session = Depends(get_db)):
    user, job = _get_pair(db, payload.user_id, payload.job_id)
    prompt = RESUME_USER_TEMPLATE.format(
        name=user.name, target_roles=user.target_roles, additional_context=user.additional_context,
        resume_latex=user.resume_latex, position=job.position, company=job.company, location=job.location,
        salary_text=job.salary_text or "Not specified", description=job.description or "No full job description was returned by the job provider."
    )
    try:
        latex = await generate(prompt, RESUME_SYSTEM)
        # Strip accidental fences if model ignores the system instruction.
        latex = re.sub(r"^```(?:latex|tex)?\s*", "", latex, flags=re.I | re.M)
        # Remove closing fence
        latex = re.sub(r"\s*```$", "", latex, flags=re.I | re.M)
        latex = latex.strip()
        
        filename = f"resume_{user.id}_{job.id}_{uuid.uuid4().hex[:8]}"
        pdf = _compile_latex(latex, filename)
        (OUT / f"{filename}.tex").write_text(latex, encoding="utf-8")
        return {"filename": filename, "latex": latex, "pdf_url": f"/api/documents/{filename}/pdf"}
    except HTTPException: raise
    except Exception as exc: raise HTTPException(502, f"Resume generation failed: {exc}")

@router.post("/documents/cover-letter")
async def cover_letter(payload: CoverLetterRequest, db: Session = Depends(get_db)):
    user, job = _get_pair(db, payload.user_id, payload.job_id)
    prompt = COVER_USER_TEMPLATE.format(
        name=user.name, target_roles=user.target_roles, additional_context=user.additional_context,
        resume_latex=user.resume_latex, position=job.position, company=job.company, location=job.location,
        salary_text=job.salary_text or "Not specified", description=job.description or "No full job description was returned by the job provider."
    )
    try:
        letter = await generate(prompt, COVER_SYSTEM)
        filename = f"cover_letter_{user.id}_{job.id}_{uuid.uuid4().hex[:8]}.txt"
        (OUT / filename).write_text(letter, encoding="utf-8")
        return {"filename": filename, "cover_letter": letter, "download_url": f"/api/documents/{filename}/download"}
    except Exception as exc: raise HTTPException(502, f"Cover letter generation failed: {exc}")

@router.get("/documents/{filename}/pdf")
def download_pdf(filename: str):
    if not re.fullmatch(r"resume_\d+_\d+_[a-f0-9]+", filename):
        raise HTTPException(400, "Invalid filename.")
    path = OUT / f"{filename}.pdf"
    if not path.exists(): raise HTTPException(404, "PDF not found.")
    return FileResponse(path, media_type="application/pdf", filename="tailored_resume.pdf")

@router.get("/documents/{filename}/download")
def download_text(filename: str):
    if not re.fullmatch(r"cover_letter_\d+_\d+_[a-f0-9]+\.txt", filename):
        raise HTTPException(400, "Invalid filename.")
    path = OUT / filename
    if not path.exists(): raise HTTPException(404, "File not found.")
    return FileResponse(path, media_type="text/plain", filename="cover_letter.txt")
