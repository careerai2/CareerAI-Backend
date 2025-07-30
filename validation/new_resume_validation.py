from pydantic import BaseModel
from typing import List, Optional

class ResumeRenderContext(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    linkedin: Optional[str] = None
    github: Optional[str] = None
    website: Optional[str] = None

    summary: Optional[str] = None
    skills: List[str] = []
    languages: List[str] = []

    education: List[str] = []
    work_experience: List[str] = []
    internships: List[str] = []
    projects: List[str] = []
    por: List[str] = []  # positions of responsibility
    achievements: List[str] = []
    extra_curricular: List[str] = []

    # Optional: footer or additional info
    footer_note: Optional[str] = None
