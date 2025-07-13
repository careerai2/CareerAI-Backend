from fastapi import Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db import get_session
from models.user_model import User
from validation.user_types import UserCreate, UserLogin
from utils.jwt import create_jwt
from utils.securiy import hash_password,verify_password


async def signup_user(user_data: UserCreate, session: AsyncSession):
    try:
        # Check if user already exists
        stmt = select(User).where(User.username == user_data.username)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            return JSONResponse(
                content={"message": "Username already exists"},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # Create new user

        user_data.password = hash_password(user_data.password)
        user = User.from_orm(user_data)
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Generate JWT
        token = create_jwt(user_id=user.id, role="user")
        if not token:
            raise Exception("Failed to generate JWT token")

        return JSONResponse(
            content={"message": "User created successfully", "access_token": token},
            status_code=status.HTTP_201_CREATED
        )

    except Exception as e:
        return JSONResponse(
            content={"message": f"An error occurred: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


async def login_user(user_data:UserLogin, session: AsyncSession):
    try:
        # Check if user exists
        stmt = select(User).where(User.username == user_data.username)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        isPasswordValid = verify_password(user_data.password, user.password) 
        if not user or not isPasswordValid:
            return JSONResponse(
                content={"message": "Invalid username or password"},
                status_code=status.HTTP_401_UNAUTHORIZED
            )

        # Generate JWT
        token = create_jwt(user_id=user.id, role="user")
        if not token:
            raise Exception("Failed to generate JWT token")

        return JSONResponse(
            content={"message": "Login successful", "access_token": token},
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        return JSONResponse(
            content={"message": f"An error occurred: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



# get user by ID
async def get_user_by_id(user_id: int, session: AsyncSession = Depends(get_session)):
    try:
        stmt = select(User.id, User.username, User.intro).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        print(user)

        if not user:
            return JSONResponse(
                content={"message": "User not found"},
                status_code=status.HTTP_404_NOT_FOUND
            )

        return JSONResponse(
            content=user.model_dump(),
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        return JSONResponse(
            content={"message": f"An error occurred: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )