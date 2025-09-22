
from enum import Enum
from typing import Literal

class Fields(str, Enum):
    Summary = "summary"
    EDUCATION = "Education"
    INTERNSHIP = "internship"
    WORKEX = "WorkEx"
    POR = "POR"
    SCHOLASTIC_ACHIEVEMENT = "Scholastic Achievement"
    EXTRA_CURRICULAR = "Extra Curricular"

def agent_map(field: Fields) -> str:

    agent_fields = [Fields.EDUCATION, Fields.INTERNSHIP, Fields.WORKEX, Fields.POR, Fields.SCHOLASTIC_ACHIEVEMENT, Fields.EXTRA_CURRICULAR, Fields.Summary]
    
    if field not in agent_fields:
        return "main_assistant"
    
    return {
        Fields.EDUCATION: "education_assistant",
        Fields.INTERNSHIP: "internship_assistant",
        Fields.WORKEX: "workex_assistant",
        Fields.POR: "position_of_responsibility_assistant",
        Fields.SCHOLASTIC_ACHIEVEMENT: "scholastic_achievement_assistant",
        Fields.EXTRA_CURRICULAR: "extra_curricular_assistant"
    }.get(field, "main_assistant")



ResumeSectionLiteral = Literal[
    "education_entries",
    "work_experiences",
    "internships",
    "achievements",
    "positions_of_responsibility",
    "extra_curriculars",
    "certifications",
    "academic_projects",
    "None"
]

def resume_section_map(field: Fields) -> ResumeSectionLiteral:
    
    mapping = {
        Fields.EDUCATION: "education_entries",
        Fields.INTERNSHIP: "internships",
        Fields.WORKEX: "work_experiences",
        Fields.POR: "positions_of_responsibility",
        Fields.SCHOLASTIC_ACHIEVEMENT: "achievements",
        Fields.EXTRA_CURRICULAR: "extra_curriculars"
    }
    return mapping.get(field,"None")






# agent_map = {
#     # "Main": "main",
#     "Internship": "internship",
#     "Work Experience": "work_experience",
#     "Education": "education",
#     "POR": "position_of_responsibility",
#     "WorkEx": "workex",
#     "Extra Curricular": "extra_curricular",
#     "Scholastic Achievement": "scholastic_achievement"
# }