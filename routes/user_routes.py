from fastapi import APIRouter, Request,Depends
from controllers.user_controller import *
from sqlalchemy.ext.asyncio import AsyncSession
from validation.user_types import * 
from db import get_database
from postgress_db import get_postgress_db



router = APIRouter(prefix="/api/user", tags=["users"])



# @router.get("/get-user")
# async def get_user(request: Request, session: AsyncSession = Depends(get_session)):
#     user_id = request.state.user.id
#     return await get_user_by_id(user_id,session)



# @router.post("/add-education")
# async def addEducation(request: Request, education_data: EducationCreate, session: AsyncSession = Depends(get_session)):
#     user_id = request.state.user.id
#     return await add_education(user_id, education_data, session)


# @router.post("/add-work-experience")
# async def addWorkExperience(request: Request, work_experience_data: WorkExperience, session: AsyncSession = Depends(get_session)):
#     user_id = request.state.user.id
#     return await add_work_experience(user_id, work_experience_data, session)


# @router.post("/add-internship")
# async def addInternship(request: Request, internship_data: InternshipCreate, session: AsyncSession = Depends(get_session)):
#     user_id = request.state.user.id
#     return await add_internship(user_id, internship_data, session)


# @router.post("/add-achievement")
# async def addAchievement(request: Request, achievement_data: AchievementCreate, session: AsyncSession = Depends(get_session)):
#     user_id = request.state.user.id
#     return await add_achievement(user_id, achievement_data, session)


# @router.post("/add-por")
# async def addPositionOfResponsibility(request: Request, position_data: PositionOfResponsibilityCreate, session: AsyncSession = Depends(get_session)):
#     user_id = request.state.user.id
#     return await add_por(user_id, position_data, session)


# @router.post("/add-extracurricular")
# async def addExtracurricular(request: Request, extracurricular_data: ExtracurricularCreate, session: AsyncSession = Depends(get_session)):
#     user_id = request.state.user.id
#     return await add_extracurricular(user_id, extracurricular_data, session)



# @router.get("/get-resume")
# async def getResume(request: Request, session: AsyncSession = Depends(get_session)):
#     user_id = request.state.user.id
#     return await get_all_resume(user_id, session)



class ResumeInput(BaseModel):
    user_input: str
    template: str = "MinimalistTemplate"   

@router.post("/parse-audio-input")
async def parseAudioInput(request: Request, resume_input: ResumeInput, db: AsyncIOMotorDatabase = Depends(get_database)):
    # print(f"User Input for Resume Extraction: {resume_input.user_input}")
    user_id = request.state.user["_id"]
    return await extract_resume_from_audio(resume_input.user_input, resume_input.template, user_id, db)



@router.get("/get-resume/{resume_id}")
async def get_resume(
    resume_id: str,
    request: Request,
    session: AsyncSession = Depends(get_database)
):
    user_id = request.state.user["_id"]
    return await get_resume_by_Id(resume_id, user_id, session)




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



