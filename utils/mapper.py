
from enum import Enum
from typing import Literal

class Fields(str, Enum):
    Summary = "Summary"
    EDUCATION = "Education"
    INTERNSHIP = "Internship"
    WORKEX = "WorkEx"
    POR = "POR"
    SCHOLASTIC_ACHIEVEMENT = "Scholastic Achievement"
    EXTRA_CURRICULAR = "Extra Curricular"
    ACADEMIC_PROJECT = "Academic Projects"

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
        Fields.EXTRA_CURRICULAR: "extra_curriculars",
        Fields.Summary: "summary",
        Fields.ACADEMIC_PROJECT: "academic_projects"
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


Section_MAPPING = {
    "internships": "Internship Document Formatting Guidelines",
    "work_experiences": "Work Experience Document Formatting Guidelines",
    "positions_of_responsibility": "Position of Responsibility Document Formatting Guidelines",
    "academic_projects": ""
}

Sub_Section_MAPPING = {
    "internships": "Schema Requirements & Formatting Rules",
     "work_experiences": "Work Experience Document Formatting Guidelines",
    "positions_of_responsibility": "Position of Responsibility Document Formatting Guidelines",
    "academic_projects": ""
    
}




FIELD_MAPPING_Bullet = {
    "internships": "Internship Work Description Bullets",
    "work_experiences": "Work Experience Description Bullets",
    "positions_of_responsibility": "Position of Responsibility Description Bullets",
    "academic_projects": "Academic Project Description Bullets"
}