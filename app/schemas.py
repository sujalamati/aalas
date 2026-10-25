from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    target_roles: str = "Software Engineer"
    locations: str = "Bengaluru"
    job_type: str = "full time"
    salary_min: Optional[int] = Field(default=None, ge=0)
    salary_currency: str = "INR"
    experience_level: str = "entry level"
    additional_context: str = ""

class UserUpdate(BaseModel):
    name: Optional[str] = None
    target_roles: Optional[str] = None
    locations: Optional[str] = None
    job_type: Optional[str] = None
    salary_min: Optional[int] = Field(default=None, ge=0)
    salary_currency: Optional[str] = None
    experience_level: Optional[str] = None
    additional_context: Optional[str] = None

class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    target_roles: str
    locations: str
    job_type: str
    salary_min: Optional[int]
    salary_currency: str
    experience_level: str
    resume_uploaded: bool
    additional_context: str
    class Config:
        from_attributes = True

class JobOut(BaseModel):
    id: int
    position: str
    company: str
    location: str
    posted_date: Optional[str]
    salary_text: str
    salary_min: Optional[float]
    salary_max: Optional[float]
    job_url: str
    company_logo: Optional[str]
    ago_time: Optional[str]
    description: str
    relevance_score: Optional[float] = None
    class Config:
        from_attributes = True

class SearchRequest(BaseModel):
    refresh: bool = True
    limit: int = Field(default=25, ge=1, le=100)

class TailorRequest(BaseModel):
    user_id: int
    job_id: int

class CoverLetterRequest(BaseModel):
    user_id: int
    job_id: int
