from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Integer, Float, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.db import Base

EMBEDDING_DIM = 1024  # Ollama embedding model dimension; configured embedding model must match.

def utcnow():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), default="Sujal Sunil Amati")
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, default="sujal5amati@gmail.com")
    target_roles: Mapped[str] = mapped_column(Text, default="Software Engineer")
    locations: Mapped[str] = mapped_column(Text, default="Bengaluru")
    job_type: Mapped[str] = mapped_column(String(80), default="full time")
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(8), default="INR")
    experience_level: Mapped[str] = mapped_column(String(80), default="entry level")
    resume_latex: Mapped[str] = mapped_column(Text, default="")
    additional_context: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan")

    @property
    def resume_uploaded(self) -> bool:
        return bool(self.resume_latex and self.resume_latex.strip())

class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("user_id", "job_url", name="uq_user_job_url"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    position: Mapped[str] = mapped_column(Text)
    company: Mapped[str] = mapped_column(String(240), default="Unknown")
    location: Mapped[str] = mapped_column(String(240), default="Not specified")
    posted_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    salary_text: Mapped[str] = mapped_column(String(240), default="Not specified")
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    job_url: Mapped[str] = mapped_column(Text)
    company_logo: Mapped[str | None] = mapped_column(Text, nullable=True)
    ago_time: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    embedding: Mapped[list | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    user = relationship("User", back_populates="jobs")
