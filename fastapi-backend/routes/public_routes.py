from fastapi import APIRouter,Depends
from controllers.user_controller import signup_user,login_user
from validation.user_types import UserCreate, UserLogin
from sqlalchemy.ext.asyncio import AsyncSession
from db import get_session

router = APIRouter(prefix="/api", tags=["users"])

@router.post("/signup")
async def create_user(user_data: UserCreate, session: AsyncSession = Depends(get_session)):
    return await signup_user(user_data,session)

@router.post("/login")
async def userLogin(user_data: UserLogin, session: AsyncSession = Depends(get_session)):
    return await login_user(user_data, session)
