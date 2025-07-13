from fastapi import APIRouter, Request,Depends
from controllers.user_controller import *
from sqlalchemy.ext.asyncio import AsyncSession
from validation.user_types import * 
from db import get_session




router = APIRouter(prefix="/api/user", tags=["users"])



@router.get("/get-user")
async def get_user(request: Request, session: AsyncSession = Depends(get_session)):
    user_id = request.state.user.id
    return await get_user_by_id(user_id,session)


@router.post("/add-education")
async def addEducation(request: Request, education_data: EducationCreate, session: AsyncSession = Depends(get_session)):
    user_id = request.state.user.id
    return await add_education(user_id, education_data, session)


@router.post("/add-work-experience")
async def addWorkExperience(request: Request, work_experience_data: WorkExperience, session: AsyncSession = Depends(get_session)):
    user_id = request.state.user.id
    return await add_work_experience(user_id, work_experience_data, session)


@router.post("/add-internship")
async def addInternship(request: Request, internship_data: InternshipCreate, session: AsyncSession = Depends(get_session)):
    user_id = request.state.user.id
    return await add_internship(user_id, internship_data, session)


@router.post("/add-achievement")
async def addAchievement(request: Request, achievement_data: AchievementCreate, session: AsyncSession = Depends(get_session)):
    user_id = request.state.user.id
    return await add_achievement(user_id, achievement_data, session)


@router.post("/add-por")
async def addPositionOfResponsibility(request: Request, position_data: PositionOfResponsibilityCreate, session: AsyncSession = Depends(get_session)):
    user_id = request.state.user.id
    return await add_por(user_id, position_data, session)


@router.post("/add-extracurricular")
async def addExtracurricular(request: Request, extracurricular_data: ExtracurricularCreate, session: AsyncSession = Depends(get_session)):
    user_id = request.state.user.id
    return await add_extracurricular(user_id, extracurricular_data, session)

@router.get("/get-resume")
async def getResume(request: Request, session: AsyncSession = Depends(get_session)):
    user_id = request.state.user.id
    return await get_resume(user_id, session)
