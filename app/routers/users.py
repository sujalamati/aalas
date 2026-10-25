from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User
from app.schemas import UserCreate, UserUpdate, UserOut

router = APIRouter(tags=["users"])

# Resume LaTeX source is stored in the database, but uploaded as a file so clients
# do not have to escape multiline source inside JSON strings.
MAX_RESUME_BYTES = 1_000_000  # 1 MB

@router.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter_by(email=payload.email).first():
        raise HTTPException(409, "A profile with this email already exists.")
    user = User(**payload.model_dump())
    db.add(user); db.commit(); db.refresh(user)
    return user

@router.post("/users/{user_id}/resume", status_code=200)
async def upload_resume(
    user_id: int,
    file: UploadFile = File(..., description="Upload the user's LaTeX resume (.tex file)"),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found.")

    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".tex"):
        raise HTTPException(400, "Resume must be uploaded as a .tex file.")

    try:
        raw = await file.read(MAX_RESUME_BYTES + 1)
    finally:
        await file.close()

    if not raw:
        raise HTTPException(400, "The uploaded resume file is empty.")
    if len(raw) > MAX_RESUME_BYTES:
        raise HTTPException(413, "Resume file is too large. Maximum size is 1 MB.")
    if b"\x00" in raw:
        raise HTTPException(400, "The uploaded file does not appear to be a text-based LaTeX file.")
    try:
        latex_source = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "Resume must be a UTF-8 encoded .tex file.")

    if not latex_source.strip():
        raise HTTPException(400, "The uploaded resume file contains no LaTeX source.")

    # Replace the stored resume atomically; no user-controlled filename is used as a path.
    user.resume_latex = latex_source
    db.commit()
    db.refresh(user)
    return {
        "message": "Resume uploaded successfully.",
        "filename": filename,
        "size_bytes": len(raw),
        "resume_uploaded": True,
    }


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user: raise HTTPException(404, "User not found.")
    return user

@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user: raise HTTPException(404, "User not found.")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    db.commit(); db.refresh(user)
    return user
