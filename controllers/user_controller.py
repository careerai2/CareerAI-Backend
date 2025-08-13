from fastapi import Depends, status
from fastapi.responses import JSONResponse,Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,or_,desc
# from db import get_session
from models.user_model import *
from validation.user_types import *
from utils.jwt import create_jwt
from utils.security import hash_password,verify_password
from typing import Dict, Any, List,Type
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi.responses import JSONResponse
from fastapi import status
from bson import ObjectId
from pymongo import ReturnDocument
from validation.user_types import UserSignup,GoogleAuth_Input
from utils.jwt import create_jwt
from utils.security import hash_password
from redis_config import redis_client as r
import json 
from utils.convert_objectIds import convert_objectids
from models.resume_model import ResumeLLMSchema
from sqlalchemy.ext.asyncio import AsyncSession
from models.chat_msg_model import ChatMessage

async def signup_user(user_data: UserSignup, db: AsyncIOMotorDatabase):
    try:
        print("user data =", user_data  )
        users_collection = db.get_collection("users")

        # Check if user with same email or name exists
        existing_user = await users_collection.find_one({
            "$or": [
                {"email": user_data.email},
                {"username": user_data.username}
            ]
        })

        if existing_user:
            return JSONResponse(
                content={"message": "Username or email already exists"},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # Hash password
        hashed_password = hash_password(user_data.password)

        user_dict = user_data.model_dump()
        user_dict["password"] = hashed_password

        # Insert user
        insert_result = await users_collection.insert_one(user_dict)

        # Generate JWT
        token = create_jwt(user_id=str(insert_result.inserted_id), role="user")
        if not token:
            raise Exception("Failed to generate JWT token")

        return JSONResponse(
            content={"message": "User created successfully", "access_token": token, "role": "user"},
            status_code=status.HTTP_201_CREATED
        )

    except Exception as e:
        print(f"Error during user signup: {e}")
        return JSONResponse(
            content={"message": f"An error occurred: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


async def login_user(user_data: UserLogin, db: AsyncIOMotorDatabase):
    try:
        users_collection = db.get_collection("users")

        # Find user by email
        user = await users_collection.find_one({"email": user_data.email})
        if not user:
            return JSONResponse(
                content={"message": "Invalid username or password"},
                status_code=status.HTTP_401_UNAUTHORIZED
            )

        # Check password
        if not verify_password(user_data.password, user["password"]):
            return JSONResponse(
                content={"message": "Invalid username or password"},
                status_code=status.HTTP_401_UNAUTHORIZED
            )

        # Generate JWT
        token = create_jwt(user_id=str(user["_id"]), role="user")
        if not token:
            raise Exception("Failed to generate JWT token")

        return JSONResponse(
            content={"message": "Login successful", "access_token": token, "role": "user"},
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        return JSONResponse(
            content={"message": f"An error occurred: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


async def google_auth(user_data: GoogleAuth_Input, db: AsyncIOMotorDatabase):
    try:
        users_collection = db.get_collection("users")
        
        existing_user = await users_collection.find_one({"email": user_data.email})

        if existing_user:
            if existing_user.get("auth_provider") != "google":
                return JSONResponse(
                    {"message": "Email already registered with password"},
                    status_code=status.HTTP_409_CONFLICT
                )
            
            token = create_jwt(user_id=str(existing_user["_id"]), role="user")
            return JSONResponse(
                {"message": "Login successful", "access_token": token, "role": "user"},
                status_code=status.HTTP_200_OK
            )

        # Create new user
        new_user = {
            "email": user_data.email,
            "username": user_data.name,
            "profile_picture": user_data.picture,
            "auth_provider": "google",
            "password": None,
            "email_verified": True
        }

        insert_result = await users_collection.insert_one(new_user)
        token = create_jwt(user_id=str(insert_result.inserted_id), role="user")

        return JSONResponse(
            {"message": "User created successfully", "access_token": token, "role": "user"},
            status_code=status.HTTP_201_CREATED
        )

    except Exception as e:
        print(f"Error during Google auth: {e}")
        return JSONResponse(
            {"message": "Internal server error"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



# get user by ID
async def get_user_by_id(user_id: int, session: AsyncSession):
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
async def get_all_resume(user_id: int, session: AsyncSession):
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
    
        
#extract resume from user audio input
from assistant.resume.parse_userAudio_input import parse_user_audio_input
from validation.resume_validation import ResumeModel


async def extract_resume_from_audio(user_input: str, template: str, user_id: str, db: AsyncIOMotorDatabase):
    try:
        # Call your parsing logic — assuming it returns a valid SQLModel instance
        resume_entry: ResumeModel = await parse_user_audio_input(user_input, user_id)

        # Save to db
        resume = await db.get_collection("resumes").insert_one({
            "user_id": user_id,
            **resume_entry.model_dump(),
            "template": template
        })

        # Update Redis cache
        r.set(f"resume:{user_id}:{resume.inserted_id}", json.dumps({**convert_objectids(resume_entry.model_dump()), "template": template}))

        # Return serialized response
        return JSONResponse(
            content={
                "message": "Resume extracted successfully",
                "resume_id": str(resume.inserted_id)
            },
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        return JSONResponse(
            content={"message": f"An error occurred while extracting resume: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        

async def get_resume_by_Id(resume_id: str, user_id: str, db: AsyncIOMotorDatabase):
    try:
        # Fetch the resume from the database
        if not ObjectId.is_valid(resume_id):
            return JSONResponse(
                content={"message": "Invalid resume ID"},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        
        try:
        # Check Redis cache first (Don't forget to delete the cache when updating the resume)
            cached_resume = r.get(f"resume:{user_id}:{resume_id}")
            if cached_resume:
                # print(f"Cache hit for resume {resume_id}")
                resume_data = json.loads(cached_resume)
                return JSONResponse(
                    content=resume_data,
                    status_code=status.HTTP_200_OK
                )
        except Exception as e:
            print(f"Error checking Redis cache: {e}")
            # Fallback to database if cache check 
            
            
        # Fetch from MongoDB
        resume_collection = db.get_collection("resumes")
        resume = await resume_collection.find_one({"_id": ObjectId(resume_id), "user_id": user_id})

        if not resume:
            return JSONResponse(
                content={"message": "Resume not found"},
                status_code=status.HTTP_404_NOT_FOUND
            )

        # Convert to ResumeModel instance
        resume_model = ResumeLLMSchema(**resume)
        
        try:
            # Cache the resume in Redis
            r.set(f"resume:{user_id}:{resume_id}", json.dumps(convert_objectids(resume_model.model_dump())))

        except Exception as e:
            print(f"Error caching resume: {e}")
            

        return JSONResponse(
            content=resume_model.model_dump(),
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        print(f"Error fetching resume: {e}")
        return JSONResponse(
            content={"message": f"An error occurred while fetching resume: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
async def get_resume_chat_msgs(resume_id: str, user_id: str, db: AsyncSession):
    try:
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.resume_id == resume_id)
            .where(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.timestamp.asc())  # oldest first for chat history
        )
        
        chat_messages = result.scalars().all()
        
        # Map sender_role to sender and type
        def map_sender_role(role: str):
            if role == "assistant":
                return "Agent", "received"
            elif role == "user":
                return "User", "sent"
            else:
                return "System", "system"
        
        serialized_msgs = []
        for msg in chat_messages:
            sender, mtype = map_sender_role(msg.sender_role)
            serialized_msgs.append({
                "id": str(msg.id),
                "sender": sender,
                "text": msg.message,
                "type": mtype,
                "timestamp": msg.timestamp.isoformat()
            })
        
        return JSONResponse(
            content={"messages": serialized_msgs},
            status_code=status.HTTP_200_OK
        )
    except Exception as e:
        print(f"Error fetching chat messages: {e}")
        return JSONResponse(
            content={"message": f"An error occurred while fetching chat messages: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
        

async def get_all_resumes_by_user(user_id: str, db: AsyncIOMotorDatabase):
    try:
        resume_collection = db.get_collection("resumes")

        # Project only title and template fields (+ _id if needed)
        cursor = resume_collection.find(
            {"user_id": user_id},
            {"title": 1, "template": 1,"_id":1}  # include only these fields
        )
        resumes = await cursor.to_list(length=None)

        # Convert ObjectId to string if _id is included
        for resume in resumes:
            resume["_id"] = str(resume["_id"])

        return JSONResponse(
            content={"resumes": resumes},
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        return JSONResponse(
            content={"message": f"An error occurred while fetching resumes: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )