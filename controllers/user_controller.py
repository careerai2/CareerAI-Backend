from fastapi import Depends, status,UploadFile, File
from fastapi.responses import JSONResponse,Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select,or_,desc
from models.user_model import *
from validation.user_types import *
from utils.extract_pdf import extract_text_from_pdf
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
import random
from utils.send_otp import send_otp_email
from assistant.resume.parse_userAudio_input import parse_user_audio_input
from validation.resume_validation import ResumeModel



def generate_otp() -> str:
    return str(random.randint(100000, 999999))

async def signup_user(user_data: UserSignup, db: AsyncIOMotorDatabase):
    try:
        print("user data =", user_data  )
        users_collection = db.get_collection("users")

        # Check if user with same email or name exists
        existing_user = await users_collection.find_one({
            "$or": [
                {"email": user_data.email},
                {"username": user_data.name}
            ]
        })

        if existing_user and existing_user.get("email_verified", False)  == True:
            return JSONResponse(
                content={"message": "Username or email already exists"},
                status_code=status.HTTP_400_BAD_REQUEST
            )
        elif existing_user and existing_user.get("email_verified", False)  == False:
            hashed_password = hash_password(user_data.password)

            existing_user["password"] = hashed_password
            existing_user["email_verified"] = False

            otp = generate_otp()
            existing_user["otp"] = otp

            # Send OTP to user's email
            res = await send_otp_email(user_data.email, otp)

            print(f"Response for {otp}", res)

            # Insert user
            await users_collection.update_one({"_id": existing_user["_id"]}, {"$set": existing_user})

            return JSONResponse(
                content={"message": "OTP sent to your email"},
                status_code=status.HTTP_201_CREATED
            )
            

        # Hash password
        hashed_password = hash_password(user_data.password)

        user_dict = user_data.model_dump()
        user_dict["password"] = hashed_password
        user_dict["email_verified"] = False

        otp = generate_otp()
        user_dict["otp"] = otp

        # Send OTP to user's email
        res = await send_otp_email(user_data.email, otp)

        print(f"Response for {otp}", res)

        # Insert user
        await users_collection.insert_one(user_dict)
        
        return JSONResponse(
            content={"message": "OTP sent to your email"},
            status_code=status.HTTP_201_CREATED
        )

    except Exception as e:
        print(f"Error during user signup: {e}")
        return JSONResponse(
            content={"message": f"An error occurred: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


async def verify_otp(otp_data: OtpVerification, db: AsyncIOMotorDatabase):
    try:
        print("OTP verification data =", otp_data)
        users_collection = db.get_collection("users")

        # Find user with the given email and OTP
        existing_user = await users_collection.find_one({
            "email": otp_data.email,
            "otp": otp_data.otp
        })

        if not existing_user:
            return JSONResponse(
                content={"message": "Invalid OTP or user not found"},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # Update user to mark email as verified and remove OTP
        update_result = await users_collection.update_one(
            {"_id": existing_user["_id"]},
            {"$set": {"email_verified": True}, "$unset": {"otp": ""}}
        )

        if update_result.modified_count == 0:
            return JSONResponse(
                content={"message": "Failed to verify email"},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Generate JWT
        token = create_jwt(user_id=str(existing_user["_id"]), role="user")
        if not token:
            raise Exception("Failed to generate JWT token")

        return JSONResponse(
            content={
                "message": "Email verified successfully",
                "access_token": token,
                "role": "user"
            },
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        print(f"Error during OTP verification: {e}")
        return JSONResponse(
            content={"message": f"An error occurred: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


async def login_user(user_data: UserLogin, db: AsyncIOMotorDatabase):
    try:
        users_collection = db.get_collection("users")

        # Find user by email
        user = await users_collection.find_one({"email": user_data.email, "email_verified": True})

        if not user:
            return JSONResponse(
                content={"message": "User not found.SignUp please"},
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
async def get_user_by_id(user_id: int, db: AsyncIOMotorDatabase):
    try:
        user = await db["users"].find_one({"_id": user_id})
        # print(user)

        if not user:
            return JSONResponse(
                content={"message": "User not found"},
                status_code=status.HTTP_404_NOT_FOUND
            )

        user_data = {
            # "id": user["_id"],
            "email": user["email"],
            "name": user["name"],
            "industries": user.get("industries", []),
            # "intro": user["intro"]
        }

        return JSONResponse(
            content={"user": user_data},
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        return JSONResponse(
            content={"message": f"An error occurred: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        


async def create_resume(template: str, tailoring_keys: list[str], user_id: str, db: AsyncIOMotorDatabase, file: Optional[UploadFile] = File(None)):
    try:
        
        user = await db.get_collection("users").find_one({"_id": ObjectId(user_id)})

        user_input = ""
        
        if user and user.get("brief"):    
            user_input = user["brief"]


        if file:
            resume_input = await extract_text_from_pdf(file)
            user_input = user_input + "\n" + resume_input if resume_input else ""
        elif user.get("base_resume"):
            user_input += "\n" + user["base_resume"]


        # print(file,tailoring_keys,user_input)
        # Call your parsing logic — assuming it returns a valid SQLModel instance
        resume_entry: ResumeLLMSchema = await parse_user_audio_input(user_input,user_id)

        # Save to db
        resume = await db.get_collection("resumes").insert_one({
            "user_id": user_id,
            **resume_entry.model_dump(),
            "tailoring_keys": tailoring_keys,
            "template": template or "",
            "created_at": datetime.now().isoformat(timespec="milliseconds") + "Z",
            "updated_at": datetime.now().isoformat(timespec="milliseconds") + "Z"
        })
        

        # Update Redis cache
        r.set(f"resume:{user_id}:{resume.inserted_id}", json.dumps({**convert_objectids(resume_entry.model_dump()),"tailoring_keys": tailoring_keys, "template": template}))

        # Return serialized response
        return JSONResponse(
            content={
                "message": "Resume extracted successfully",
                "resume_id": str(resume.inserted_id)
            },
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        print(f"Error creating resume: {e}")
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


async def delete_resume_by_Id(resume_id: str, user_id: str, db: AsyncIOMotorDatabase):
    try:
        r.delete(f"resume:{user_id}:{resume_id}")  # Remove from Redis cache
        
        resumes = await db.get_collection("resumes").delete_one({"_id": ObjectId(resume_id), "user_id": user_id})
        if resumes.deleted_count == 0:
            return JSONResponse(
                content={"message": "Resume not found"},
                status_code=status.HTTP_404_NOT_FOUND
            )
        return JSONResponse(
            content={"message": "Resume deleted successfully"},
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        print(f"Error deleting resume: {e}")
        return JSONResponse(
            content={"message": f"An error occurred while deleting resume: {str(e)}"},
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
            {"title": 1, "template": 1,"_id":1,"status": 1,"updated_at":1}  # include only these fields
        )
        resumes = await cursor.to_list(length=None)

        # Convert ObjectId to string if _id is included
        for resume in resumes:
            resume["_id"] = str(resume["_id"])

        return JSONResponse(
            content=resumes,
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        return JSONResponse(
            content={"message": f"An error occurred while fetching resumes: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



async def set_preferences_for_user(user_id: str, preferences: UserPreferences, db: AsyncIOMotorDatabase,file: Optional[UploadFile] = File(None)):
    try:
        
        # print(preferences)
        # print(file.filename if file else None)
        
        
        # return
        user = await db["users"].find_one({"_id": user_id})
        # print(user)

        if not user:
            return JSONResponse(
                content={"message": "User not found"},
                status_code=status.HTTP_404_NOT_FOUND
            )
            
        update_fields = preferences.model_dump(exclude_none=True)
        
        if file:
            file_data = await extract_text_from_pdf(file)
            # print(f"Extracted text from PDF: {file_data[:10000]}...")  # debug first 100 chars
            update_fields["base_resume"] = file_data if file_data else None
            update_fields["file_name"] = file.filename if file else None

        if not update_fields:
            return JSONResponse(
                content={"message": "No valid preferences provided to update"},
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # Update user preferences
        result = await db["users"].update_one({"_id": user_id}, {"$set": update_fields})

        if result.modified_count == 0:
            return JSONResponse(
                content={"message": "No changes made to user preferences"},
                status_code=status.HTTP_200_OK
            )

        return JSONResponse(
            content={"message": "User preferences updated successfully"},
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        print(f"Error updating user preferences: {e}")
        return JSONResponse(
            content={"message": f"An error occurred while updating user preferences: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
        
        
# get user preferences
async def get_user_preferences(user_id: int, db: AsyncIOMotorDatabase):
    try:
        user = await db["users"].find_one({"_id": user_id})
        # print(user)

        if not user:
            return JSONResponse(
                content={"message": "User not found"},
                status_code=status.HTTP_404_NOT_FOUND
            )

        user_pref = {
            "industries": user["industries"],
            "brief": user["brief"],
            "level": user.get("level", None),
            "fileName": user.get("file_name", None)
        }

        return JSONResponse(
            content= user_pref,
            status_code=status.HTTP_200_OK
        )

    except Exception as e:
        return JSONResponse(
            content={"message": f"An error occurred: {str(e)}"},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
