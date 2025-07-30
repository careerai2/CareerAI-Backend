from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from sqlalchemy import Column, JSON

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: Optional[str]
    phone_number: Optional[str] = None
    password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    resumes: List["Resume"] = Relationship(back_populates="user")


class Resume(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")

    # Resume content
    resume_data: Optional[str] = None
    summary: Optional[str] = None
    skills: Optional[List[str]] = Field(default_factory=list, sa_column=Column(JSON))
    languages: Optional[List[str]] = Field(default_factory=list, sa_column=Column(JSON))

    # Metadata
    title: Optional[str] = None
    template: Optional[str] = None
    is_default: Optional[bool] = False
    visibility: Optional[str] = Field(default="private")  # private, public, unlisted
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_modified: datetime = Field(default_factory=datetime.utcnow)

    # Status and tracking
    completion_percentage: Optional[int] = 0
    is_verified: Optional[bool] = False
    views: Optional[int] = 0
    downloads: Optional[int] = 0
    rating: Optional[float] = None
    version: Optional[int] = 1
    tags: Optional[List[str]] = Field(default_factory=list, sa_column=Column(JSON))

    # File & links
    resume_pdf_url: Optional[str] = None
    external_links: Optional[List[str]] = Field(default_factory=list, sa_column=Column(JSON))

    # Relationships
    user: Optional["User"] = Relationship(back_populates="resumes")
    resume_inputs: List["ResumeInput"] = Relationship(back_populates="resume")
    education_entries: List["Education"] = Relationship(back_populates="resume")
    work_experiences: List["WorkExperience"] = Relationship(back_populates="resume")
    internships: List["Internship"] = Relationship(back_populates="resume")
    achievements: List["ScholasticAchievement"] = Relationship(back_populates="resume")
    positions_of_responsibility: List["PositionOfResponsibility"] = Relationship(back_populates="resume")
    extra_curriculars: List["ExtraCurricular"] = Relationship(back_populates="resume")


class ResumeInput(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resume.id")
    input_text: Optional[str] = None
    audio_file: Optional[str] = None
    transcribed_text: Optional[str] = None
    submitted_at: datetime = Field(default_factory=datetime.utcnow)

    resume: Optional[Resume] = Relationship(back_populates="resume_inputs")


class Education(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resume.id")
    college: str
    degree: str
    start_year: int
    end_year: int
    cgpa: float

    resume: Optional[Resume] = Relationship(back_populates="education_entries")


class WorkExperience(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resume.id")
    company_name: str
    company_description: str
    location: Optional[str] = None
    duration: Optional[str] = None
    designation: str
    designation_description: str

    resume: Optional[Resume] = Relationship(back_populates="work_experiences")
    projects: List["Project"] = Relationship(back_populates="work_experience")


class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    work_experience_id: int = Field(foreign_key="workexperience.id")
    project_name: str
    project_description: str
    description_bullets: List[str] = Field(default_factory=list, sa_column=Column(JSON))

    work_experience: Optional[WorkExperience] = Relationship(back_populates="projects")


class Internship(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resume.id")
    company_name: str
    company_description: str
    location: Optional[str] = None
    designation: str
    designation_description: str
    duration: str
    internship_work_description_bullets: List[str] = Field(default_factory=list, sa_column=Column(JSON))

    resume: Optional[Resume] = Relationship(back_populates="internships")


class ScholasticAchievement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resume.id")
    title: str
    awarding_body: Optional[str] = None
    year: Optional[int] = None
    description: Optional[str] = None

    resume: Optional[Resume] = Relationship(back_populates="achievements")


class PositionOfResponsibility(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resume.id")
    role: str
    role_description: str
    organization: str
    organization_description: str
    location: Optional[str] = None
    duration: str
    responsibilities: List[str] = Field(default_factory=list, sa_column=Column(JSON))

    resume: Optional[Resume] = Relationship(back_populates="positions_of_responsibility",sa_relationship_kwargs={"cascade": "all, delete"})


class ExtraCurricular(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resume.id")
    activity: str
    position: Optional[str] = None
    description: Optional[str] = None
    year: Optional[int] = None

    resume: Optional[Resume] = Relationship(back_populates="extra_curriculars",sa_relationship_kwargs={"cascade": "all, delete"})
