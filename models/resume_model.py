from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
from bson import ObjectId


# Helper for MongoDB ObjectId type
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        return str(v)


# ------------------- Nested Structures ------------------------

class Project(BaseModel):
    project_name: str
    project_description: str
    description_bullets: List[str] = Field(default_factory=list)


class WorkExperience(BaseModel):
    company_name: str
    company_description: str
    location: Optional[str] = None
    duration: Optional[str] = None
    designation: str
    designation_description: str
    projects: List[Project] = Field(default_factory=list)


class Internship(BaseModel):
    company_name: str
    company_description: str
    location: Optional[str] = None
    designation: str
    designation_description: str
    duration: str
    internship_work_description_bullets: List[str] = Field(default_factory=list)


class Education(BaseModel):
    college: str
    degree: str
    start_year: int
    end_year: int
    cgpa: float


class ScholasticAchievement(BaseModel):
    title: str
    awarding_body: Optional[str] = None
    year: Optional[int] = None
    description: Optional[str] = None


class PositionOfResponsibility(BaseModel):
    role: str
    role_description: str
    organization: str
    organization_description: str
    location: Optional[str] = None
    duration: str
    responsibilities: List[str] = Field(default_factory=list)


class ExtraCurricular(BaseModel):
    activity: str
    position: Optional[str] = None
    description: Optional[str] = None
    year: Optional[int] = None


class ResumeInput(BaseModel):
    input_text: Optional[str] = None
    audio_file: Optional[str] = None
    transcribed_text: Optional[str] = None
    submitted_at: datetime = Field(default_factory=datetime.utcnow)


# ------------------- Main Resume Document ------------------------

class ResumeDocument(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: str  # Reference to user collection

    resume_data: Optional[str] = None
    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)

    title: Optional[str] = None
    template: Optional[str] = None
    is_default: Optional[bool] = False
    visibility: Optional[str] = "private"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_modified: datetime = Field(default_factory=datetime.utcnow)

    completion_percentage: Optional[int] = 0
    is_verified: Optional[bool] = False
    views: Optional[int] = 0
    downloads: Optional[int] = 0
    rating: Optional[float] = None
    version: Optional[int] = 1
    tags: List[str] = Field(default_factory=list)

    resume_pdf_url: Optional[str] = None
    external_links: List[str] = Field(default_factory=list)

    resume_inputs: List[ResumeInput] = Field(default_factory=list)
    education_entries: List[Education] = Field(default_factory=list)
    work_experiences: List[WorkExperience] = Field(default_factory=list)
    internships: List[Internship] = Field(default_factory=list)
    achievements: List[ScholasticAchievement] = Field(default_factory=list)
    positions_of_responsibility: List[PositionOfResponsibility] = Field(default_factory=list)
    extra_curriculars: List[ExtraCurricular] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        allow_population_by_field_name = True
