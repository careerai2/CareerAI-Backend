from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from sqlalchemy import Column, JSON

# All user related models
# These models are used to store user data in the database

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str
    phone_number: Optional[str] = None
    password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    resume_inputs: List["ResumeInput"] = Relationship(back_populates="user")
    education_entries: List["Education"] = Relationship(back_populates="user")
    work_experiences: List["WorkExperience"] = Relationship(back_populates="user")
    internships: List["Internship"] = Relationship(back_populates="user")
    achievements: List["ScholasticAchievement"] = Relationship(back_populates="user")
    positions_of_responsibility: List["PositionOfResponsibility"] = Relationship(back_populates="user")
    extra_curriculars: List["ExtraCurricular"] = Relationship(back_populates="user")


class ResumeInput(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    input_text: Optional[str] = None
    audio_file: Optional[str] = None
    transcribed_text: Optional[str] = None
    submitted_at: datetime = Field(default_factory=datetime.utcnow)

    user: Optional[User] = Relationship(back_populates="resume_inputs")


class Education(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    college: str
    degree: str
    start_year: int
    end_year: int
    cgpa: float

    user: Optional[User] = Relationship(back_populates="education_entries")


class WorkExperience(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    company_name: str
    company_description: str
    location: Optional[str] = None
    duration: Optional[str] = None
    designation: str
    designation_description: str

    user: Optional[User] = Relationship(back_populates="work_experiences")
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
    user_id: int = Field(foreign_key="user.id")
    company_name: str
    company_description: str
    location: Optional[str] = None
    designation: str
    designation_description: str
    duration: str
    internship_work_description_bullets: List[str] = Field(default_factory=list, sa_column=Column(JSON))

    user: Optional[User] = Relationship(back_populates="internships")


class ScholasticAchievement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    title: str
    awarding_body: Optional[str] = None
    year: Optional[int] = None
    description: Optional[str] = None

    user: Optional[User] = Relationship(back_populates="achievements")


class PositionOfResponsibility(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    role: str
    role_description: str
    organization: str
    organization_description: str
    location: Optional[str] = None
    duration: str
    responsibilities: List[str] = Field(default_factory=list, sa_column=Column(JSON))

    user: Optional[User] = Relationship(back_populates="positions_of_responsibility")


class ExtraCurricular(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    activity: str
    position: Optional[str] = None
    description: Optional[str] = None
    year: Optional[int] = None

    user: Optional[User] = Relationship(back_populates="extra_curriculars")
