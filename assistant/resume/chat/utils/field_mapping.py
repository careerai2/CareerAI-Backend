# Mappers for different sections of resume and their corresponding field names in Vector DB 

class FieldMapping:
    
    INTERNSHIP = {
    "company_name": "Company Name",
    "company_description": "Company Description",
    "location": "Location",
    "designation": "Designation",
    "designation_description": "Designation Description",
    "duration": "Duration",
    "project_name": "Project Name",
    "project_description": "Project Description",
    "description_bullets": " Description Bullets",
    "tools_and_technologies": "Tools & Technologies",
    "impact": "Impact",
    "team_collaboration": "Team Collaboration",
    "learning_outcomes": "Learning Outcomes",
    }
    
    
    POR = {
        "role": "Role",
        "role_description": "Role Description",
        "organization": "Organization",
        "organization_description": "Organization Description",
        "location": "Location",
        "duration": "Duration",
        "responsibilities": "Responsibilities",
    }
    

    PROJECT = {
        "project_name": "Project Name",
        "project_description": "Project Description",
        "description_bullets": "Description Bullets",
        "duration": "Duration",
    }
    
    
    WORKEX = {
    "company_name": "Company Name",
    "company_description": "Company Description",
    "location": "Location",
    "designation": "Designation",
    "designation_description": "Designation Description",
    "duration": "Duration",
    "project_name": "Project Name",
    "project_description": "Project Description",
    "description_bullets": " Description Bullets",
    "tools_and_technologies": "Tools & Technologies",
    "impact": "Impact",
    "team_collaboration": "Team Collaboration",
    "learning_outcomes": "Learning Outcomes",
    }
    
    
    Section_MAPPING = {
    "internship": "Internships",
    
    }
    
    
    
    @classmethod
    def get(cls, section: str, field: str):
        """Safe universal getter: FieldMapping.get("POR", "role")"""
        mapping = getattr(cls, section.upper(), {})
        return mapping.get(field)
