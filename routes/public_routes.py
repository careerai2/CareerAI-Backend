from fastapi import APIRouter,HTTPException,Depends
from controllers.user_controller import signup_user,login_user
from validation.user_types import UserSignup, UserLogin
from db import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
router = APIRouter(prefix="/api", tags=["users"])



@router.post("/signup")
async def create_user(user_data: UserSignup, db: AsyncIOMotorDatabase = Depends(get_database)):
    try:
        print("Received user data for signup:", user_data)
        return await signup_user(user_data, db)
    except Exception as e:
        print(f"Error during user signup: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/login")
async def userLogin(user_data: UserLogin, db: AsyncIOMotorDatabase = Depends(get_database)):
    try:
        return await login_user(user_data, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
