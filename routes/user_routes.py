from fastapi import APIRouter, Request,Depends,Form
from controllers.user_controller import *
from sqlalchemy.ext.asyncio import AsyncSession
from validation.user_types import * 
from db import get_database
from postgress_db import get_postgress_db



router = APIRouter(prefix="/api/user", tags=["users"])



@router.get("/get-user")
async def get_user(request: Request, db: AsyncIOMotorDatabase = Depends(get_database)):
    user_id = request.state.user["_id"]
    return await get_user_by_id(user_id, db)


@router.get("/get-preferences")
async def get_preference(request: Request, db: AsyncIOMotorDatabase = Depends(get_database)):
    user_id = request.state.user["_id"]
    return await get_user_preferences(user_id, db)


class ResumeInput(BaseModel):
    file: str | None = None
    industry: str | None = None

class ResumeInput(BaseModel):
    template: str = "MinimalistTemplate"
    data: ResumeInput
    # tailoring_keys: str

@router.post("/create-resume")
async def createResume(
    request: Request,
    template: str = Form(...),
    industry: str = Form(...),
    file: Optional[UploadFile] = File(None),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    user_id = request.state.user["_id"]
    tailoring_keys = [industry]
    return await create_resume(template, tailoring_keys, user_id, db, file)

@router.get("/get-resume/{resume_id}")
async def get_resume(
    resume_id: str,
    request: Request,
    session: AsyncSession = Depends(get_database)
):
    user_id = request.state.user["_id"]
    return await get_resume_by_Id(resume_id, user_id, session)


@router.delete("/delete-resume/{resume_id}")
async def delete_resume(
    resume_id: str,
    request: Request,
    session: AsyncSession = Depends(get_database)
):
    user_id = request.state.user["_id"]
    return await delete_resume_by_Id(resume_id, user_id, session)




# @router.get("/get-resume-chat-history/{resume_id}")
# async def get__msgs(
#     resume_id: str,
#     request: Request,
#     session: AsyncSession = Depends(get_postgress_db)
# ):
#     user_id = request.state.user["_id"]
#     resume_id_str = str(resume_id) # converted MongoDB ObjectId to string
#     user_id_str = str(user_id)     # '''''
#     return await get_resume_chat_msgs(resume_id_str, user_id_str, session)


@router.get("/get-all-resume")
async def get_all_resumes(request: Request,session: AsyncSession = Depends(get_database)):
    user_id = request.state.user["_id"]
    return await get_all_resumes_by_user(user_id, session)


class PreferenceRequest(BaseModel):
    preferences: UserPreferences
    file: Optional[str] = None
    
@router.patch("/set-preference")
async def set_user_preferences(
    request: Request,
    preferences: str = Form(...),                  # JSON string in FormData
    file: Optional[UploadFile] = File(None),       # actual file
    session: AsyncSession = Depends(get_database)
):
    user_id = request.state.user["_id"]

    # Parse JSON string into Pydantic model
    prefs = UserPreferences.model_validate_json(preferences)

    return await set_preferences_for_user(
        user_id=user_id,
        preferences=prefs,
        db=session,
        file=file
    )
    
    
@router.put("/export-resume/{resume_id}")
async def set_user_preferences( resume_id: str,
    request: Request,
    session: AsyncSession = Depends(get_database)):
    user_id = request.state.user["_id"]
    return await export_resume_data(resume_id, user_id, session)
    



