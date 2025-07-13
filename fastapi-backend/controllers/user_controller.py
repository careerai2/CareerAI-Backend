from fastapi import Depends, status
from fastapi.responses import JSONResponse,Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,or_
from db import get_session
from models.user_model import *
from validation.user_types import *
from utils.jwt import create_jwt
from utils.securiy import hash_password,verify_password
from typing import Dict, Any, List,Type


async def signup_user(user_data: UserSignup, session: AsyncSession):
    try:
      

        # Check if user already exists
        stmt = select(User).where(
            or_(
                User.email == user_data.email,
                User.name == user_data.name
            )
        )
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            return JSONResponse(
                content={"message": "Username or email already exists"},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # Hash password and create user
        hashed_password = hash_password(user_data.password)
        user = User.model_validate(user_data.model_copy(update={"password": hashed_password}))
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
        
        
# add education
async def add_education(user_id: int, education_data: EducationCreate, session: AsyncSession):
    try:
        # Create new education entry
        education_entry = Education(user_id=user_id, **education_data.model_dump())
        session.add(education_entry)
        await session.commit()
        await session.refresh(education_entry)

        return JSONResponse(
            content={"message": "Education added successfully"},
            status_code=status.HTTP_201_CREATED
        )

    except Exception as e:
        return JSONResponse(
            content={"message": f"An error occurred: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



# add Work Experience
async def add_work_experience(user_id: int, work_experience_data: WorkExperienceCreate, session: AsyncSession):
    try:
        # Create new work experience entry
        work_experience_entry = WorkExperience(user_id=user_id, **work_experience_data.model_dump())
        session.add(work_experience_entry)
        await session.commit()
        await session.refresh(work_experience_entry)

        return JSONResponse(
            content={"message": "Work Experience added successfully"},
            status_code=status.HTTP_201_CREATED
        )

    except Exception as e:
        return JSONResponse(
            content={"message": f"An error occurred: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
# add Internship
async def add_internship(user_id: int, internship_data: InternshipCreate, session: AsyncSession):
    try:
        # Create new internship entry
        internship_entry = Internship(user_id=user_id, **internship_data.model_dump())

        session.add(internship_entry)
        await session.commit()
        await session.refresh(internship_entry)

        return JSONResponse(
            content={"message": "Internship added successfully"},
            status_code=status.HTTP_201_CREATED
        )

    except Exception as e:
        return JSONResponse(
            content={"message": f"An error occurred: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# add Achievement
async def add_achievement(user_id: int, achievement_data: AchievementCreate, session: AsyncSession):
    try:
        # Create new achievement entry
        achievement_entry = ScholasticAchievement(user_id=user_id, **achievement_data.model_dump())

        session.add(achievement_entry)
        await session.commit()
        await session.refresh(achievement_entry)

        return JSONResponse(
            content={"message": "Achievement added successfully"},
            status_code=status.HTTP_201_CREATED
        )

    except Exception as e:
        return JSONResponse(
            content={"message": f"An error occurred: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
        
        
# add Position of Responsibility
async def add_por(user_id: int, por_data: PositionOfResponsibilityCreate, session: AsyncSession):
    try:
        # Create new position of responsibility entry
        por_entry = PositionOfResponsibility(user_id=user_id, **por_data.model_dump())

        session.add(por_entry)
        await session.commit()
        await session.refresh(por_entry)

        return JSONResponse(
            content={"message": "Position of Responsibility added successfully"},
            status_code=status.HTTP_201_CREATED
        )

    except Exception as e:
        return JSONResponse(
            content={"message": f"An error occurred: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )   
        

# add Extracurricular
async def add_extracurricular(user_id: int, extracurricular_data: ExtracurricularCreate, session: AsyncSession):
    try:
        # Create new extracurricular entry
        extracurricular_entry = ExtraCurricular(user_id=user_id, **extracurricular_data.model_dump())

        session.add(extracurricular_entry)
        await session.commit()
        await session.refresh(extracurricular_entry)

        return JSONResponse(
            content={"message": "Extracurricular activity added successfully"},
            status_code=status.HTTP_201_CREATED
        )

    except Exception as e:
        return JSONResponse(
            content={"message": f"An error occurred: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
        
#helper function for get-resume

async def fetch_and_dump(session: AsyncSession, user_id: int, model: Type) -> List[Dict[str, Any]]:
    stmt = select(model).where(model.user_id == user_id)
    result = await session.execute(stmt)
    return [obj.model_dump() for obj in result.scalars()]


# get Resume
async def get_resume(user_id: int, session: AsyncSession):
    try:
        # Model mapping for sections
        model_map = {
            "education": Education,
            "work_experience": WorkExperience,
            "internships": Internship,
            "achievements": ScholasticAchievement,
            "positions_of_responsibility": PositionOfResponsibility,
            "extracurriculars": ExtraCurricular,
        }

        resume_data: Dict[str, Any] = {}

        # Fetch each section dynamically
        for section, model in model_map.items():
            resume_data[section] = await fetch_and_dump(session,user_id, model)

        return JSONResponse(content=resume_data, status_code=status.HTTP_200_OK)

    except Exception as e:
        return JSONResponse(
            content={"message": f"An error occurred while generating resume: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )