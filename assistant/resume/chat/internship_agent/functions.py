from langchain.tools import tool
from pydantic import BaseModel, field_validator,ValidationError
import json
from typing import Literal,Union
from models.resume_model import *
from typing import Optional, Literal
from pydantic import BaseModel, field_validator
import json
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from ..utils.common_tools import get_resume, save_resume, send_patch_to_frontend,load_kb
from ..utils.update_summar_skills import update_summary_and_skills
from ..handoff_tools import *
from redis_config import redis_client as r 
from assistant.resume.chat.utils.common_tools import human_assistance,send_patch_to_frontend
from langgraph.prebuilt import InjectedState
from models.resume_model import Internship
# from .state import InternshipState
from ..llm_model import SwarmResumeState,InternshipState

# THINKING OF PATCHES
# for the new one similar can be also done for update 
async def add_internship(thread_id: str, new_internship: Internship):
    """
    Adds a new internship to the resume and updates Redis.
    """
    try:
        # print("Adding internship:", thread_id)

        # 1. Load existing resume
        current_resume_raw = r.get(f"resume:{thread_id}")
        if current_resume_raw:
            current_resume = json.loads(current_resume_raw)
        else:
            raise ValueError("Resume not found for the given thread_id.")

        # 2. Get internships list
        current_internships = current_resume.get("internships", [])

        # print("Current internships from Redis:", current_internships)

        # 3. Check duplicate by company_name
        for i in current_internships:
            if i["company_name"].lower() == new_internship.company_name.lower():
                return {"status": "error", "message": "Internship with this company already exists."}

        # 4. Append new internship
        current_internships.append(new_internship.model_dump())
        current_resume["internships"] = current_internships

        # 5. Save back to Redis
        r.set(f"resume:{thread_id}", json.dumps(current_resume))

        user_id = thread_id.split(":")[0]

        print("User ID:", user_id)
        # print("Current Resume:", current_resume)

        await send_patch_to_frontend(user_id, current_resume)

        return {"status": "success", "message": "Internship added successfully."}

    except ValidationError as ve:
        return {"status": "error", "message": f"Validation error: {ve.errors()}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
