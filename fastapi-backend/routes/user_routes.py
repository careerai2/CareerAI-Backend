from fastapi import APIRouter, Request,Depends
from controllers.user_controller import *
from sqlalchemy.ext.asyncio import AsyncSession
from validation.user_types import * 
from db import get_session




router = APIRouter(prefix="/api/user", tags=["users"],)



@router.get("/get_user")
async def get_user(request: Request, session: AsyncSession = Depends(get_session)):
    user_id = request.state.user.id
    return await get_user_by_id(user_id,session)
