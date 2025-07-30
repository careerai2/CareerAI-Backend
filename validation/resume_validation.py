from pydantic import BaseModel, EmailStr, constr
from typing import List, Optional

PhoneNumberStr = constr(min_length=10, max_length=15)

# Note: This model is in sync with the TypeScript frontend model
class User(BaseModel):
    name: Optional[str]
    email: Optional[EmailStr]
    phone_number: Optional[str]

class Resume(BaseModel):
    title: Optional[str]
    summary: Optional[str]
    skills: Optional[List[str]]
    languages: Optional[List[str]]
    external_links: Optional[List[str]]

class Project(BaseModel):
    project_name: Optional[str]
    project_description: Optional[str]
    description_bullets: Optional[List[str]]

class WorkExperience(BaseModel):
    company_name: Optional[str]
    company_description: Optional[str]
    location: Optional[str]
    duration: Optional[str]
    designation: Optional[str]
    designation_description: Optional[str]
    projects: Optional[List[Project]]

class EducationEntry(BaseModel):
    college: Optional[str] = None
    degree: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    cgpa: Optional[float] = None

class Internship(BaseModel):
    company_name: Optional[str]
    company_description: Optional[str]
    location: Optional[str]
    designation: Optional[str]
    designation_description: Optional[str]
    duration: Optional[str]
    internship_work_description_bullets: Optional[List[str]]

class PositionOfResponsibility(BaseModel):
    role: Optional[str]
    role_description: Optional[str]
    organization: Optional[str]
    organization_description: Optional[str]
    location: Optional[str]
    duration: Optional[str]
    responsibilities: Optional[List[str]]

class Achievement(BaseModel):
    title: Optional[str]
    awarding_body: Optional[str]
    year: Optional[int]
    description: Optional[str]

class ExtraCurricular(BaseModel):
    activity: Optional[str]
    position: Optional[str]
    description: Optional[str]
    year: Optional[int]

# Final aggregated model to be returned by endpoints
class ResumeModel(BaseModel):
    user: Optional[User]
    resume: Optional[Resume]
    education_entries: Optional[List[EducationEntry]]
    work_experiences: Optional[List[WorkExperience]]
    achievements: Optional[List[Achievement]]
    positions_of_responsibility: Optional[List[PositionOfResponsibility]]
    internships: Optional[List[Internship]]
    extra_curriculars: Optional[List[ExtraCurricular]]


