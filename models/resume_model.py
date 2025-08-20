from pydantic import BaseModel, Field, EmailStr
from typing import Literal, Optional, List
from datetime import datetime
from bson import ObjectId


# Helper for MongoDB ObjectId type
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        try:
            return str(ObjectId(v))
        except Exception:
            raise ValueError("Invalid ObjectId")


# ------------------- Nested Structures ------------------------
class AcademicProject(BaseModel):
    project_name: Optional[str] = None
    project_description: Optional[str] = None
    description_bullets: Optional[List[str]] = Field(default_factory=list)
    duration: Optional[str] = None
    
    
class Project(BaseModel):
    project_name: Optional[str] = None
    project_description: Optional[str] = None
    description_bullets: Optional[List[str]] = Field(default_factory=list)

class WorkExperience(BaseModel):
    company_name: Optional[str] = None
    company_description: Optional[str] = None
    location: Optional[str] = None
    duration: Optional[str] = None
    designation: Optional[str] = None
    designation_description: Optional[str] = None
    projects: Optional[List[Project]] = Field(default_factory=list)

class Internship(BaseModel):
    company_name: Optional[str] = None
    company_description: Optional[str] = None
    location: Optional[str] = None
    designation: Optional[str] = None
    designation_description: Optional[str] = None
    duration: Optional[str] = None
    internship_work_description_bullets: Optional[List[str]] = Field(default_factory=list)

class Education(BaseModel):
    college: Optional[str] = None
    degree: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    cgpa: Optional[float] = None

class ScholasticAchievement(BaseModel):
    title: Optional[str] = None
    awarding_body: Optional[str] = None
    year: Optional[int] = None
    description: Optional[str] = None

class PositionOfResponsibility(BaseModel):
    role: Optional[str] = None
    role_description: Optional[str] = None
    organization: Optional[str] = None
    organization_description: Optional[str] = None
    location: Optional[str] = None
    duration: Optional[str] = None
    responsibilities: Optional[List[str]] = Field(default_factory=list)

class ExtraCurricular(BaseModel):
    activity: Optional[str] = None
    position: Optional[str] = None
    description: Optional[str] = None
    year: Optional[int] = None

class Certification(BaseModel):
    certification: Optional[str] = None
    description: Optional[str] = None
    issuing_organization: Optional[str] = None
    time_of_certification: Optional[int] = None

class ResumeInput(BaseModel):
    input_text: Optional[str] = None
    audio_file: Optional[str] = None
    transcribed_text: Optional[str] = None
    submitted_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


# ------------------- Main Resume Document ------------------------

class ResumeDocument(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    user_id: str  # Reference to user collection

    resume_data: Optional[str] = None
    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    
    name: Optional[str] = None  # Reference to user collection
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    tailoring_keys: List[str] = Field(default=["Consulting"])

    title: Optional[str] = None
    template: Optional[str] = None
    is_default: Optional[bool] = False
    visibility: Optional[str] = "private"
    created_at: datetime = Field(default_factory=datetime.now().isoformat())
    updated_at: datetime = Field(default_factory=datetime.now().isoformat())
    status: Literal["in-progress","completed"] = "in-progress"

    # last_modified: datetime = Field(default_factory=datetime.now().isoformat())

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
    academic_projects: List[AcademicProject] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)   

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        validate_by_name = True


# ------------------- LLM Schema for Resume Generation ------------------------
class ResumeLLMSchema(BaseModel):
    title: Optional[str] = None
    summary: Optional[str] = None
    name: Optional[str] = None  # Reference to user collection
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    tailoring_keys: List[str] = []
    total_updates: int = 0        # a flag number to check,that skills and Summary are updated # will check if it is 10 yes then update and set it 0 
    skills: List[str] = []
    interests: List[str] = []
    languages: List[str] = []
    external_links: List[str] = []
    resume_inputs: List[ResumeInput] = []
    status: Literal["in-progress","completed"] = "in-progress"  # can be in-progress, completed
    last_modified: Optional[datetime] = Field(default_factory=datetime.now().isoformat())
    education_entries: List[Education] = []
    work_experiences: List[WorkExperience] = []
    internships: List[Internship] = []
    achievements: List[ScholasticAchievement] = []
    positions_of_responsibility: List[PositionOfResponsibility] = []
    extra_curriculars: List[ExtraCurricular] = []
    certifications: List[Certification] = []
    academic_projects: List[AcademicProject] = []

    class Config:
        arbitrary_types_allowed = True
