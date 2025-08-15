from datetime import datetime
from sqlmodel import SQLModel
from pydantic import BaseModel,Field,model_validator
from typing import Optional,List

# we can also restrict what are we taking as input


class UserSignup(BaseModel):
    email:str
    name: Optional[str]
    # phone_number: Optional[str] = None
    dob: str
    password: str
    email_verified: bool = False

class OtpVerification(BaseModel):
    email: str
    otp: str

class UserLogin(BaseModel):
    email: str
    password: str
    
class GoogleAuth_Input(BaseModel):
    name: str
    email: str
    picture: str
    
    
class EducationCreate(BaseModel):
    college: str
    degree: str
    start_year: int
    end_year: int
    cgpa: float
    
    
class WorkExperienceCreate(BaseModel):
    company_name: str
    company_description: str
    location: Optional[str] = None
    duration: Optional[str] = None
    designation: str
    designation_description: str
    
    
class InternshipCreate(BaseModel):
    company_name: str
    company_description: str
    location: Optional[str] = None
    designation: str
    designation_description: str
    duration: str
    internship_work_description_bullets: list[str] = []  
    
    
class AchievementCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=100)
    awarding_body: Optional[str] = Field(None, max_length=100)
    year: Optional[int] = Field(None, description="4-digit year only", ge=1000, le=9999)
    description: Optional[str] = Field(None, max_length=500)

    # @model_validator(mode="before")
    # def check_awarding_body_with_year(cls, values):
    #     year, awarding_body = values.get("year"), values.get("awarding_body")
    #     if year and not awarding_body:
    #         raise ValueError("Awarding body must be specified if year is provided")
    #     return values


class PositionOfResponsibilityCreate(BaseModel):
    role: str
    role_description: str
    organization: str
    organization_description: str
    location: Optional[str] = None
    duration: str
    responsibilities: list[str] = []
    
    
class ExtracurricularCreate(BaseModel):
    activity: str
    position: Optional[str] = None
    description: Optional[str] = None
    year: Optional[int] = None



class UserPreferences(BaseModel):
    industries: Optional[List[str]] = []
    brief: Optional[str] = None
    fileName: Optional[str] = None
    level: Optional[str] = None
    
    # profile_picture: Optional[str] = None
    