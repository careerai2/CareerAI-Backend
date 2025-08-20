from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId
from pydantic.json_schema import JsonSchemaValue
from typing import Any
from datetime import datetime


# MongoDB ObjectId wrapper for validation
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: Any, handler: Any
    ) -> JsonSchemaValue:
        # This replaces __modify_schema__ in Pydantic v2
        json_schema = handler(core_schema)
        json_schema.update(type="string")
        return json_schema


# Model used for insertion
class UserCreate(BaseModel):
    email: EmailStr
    username: Optional[str]
    # phone_number: Optional[str]
    password: Optional[str] = None  # should be hashed before saving
    dob: Optional[str] = None  # Date of birth
    otp: Optional[int] = None  # One-time password for verification
    otp_expiry: Optional[datetime] = None  # Expiry time for OTP
    email_verified: bool = Field(default=False)  # Flag to check if email is verified
    industries: Optional[list[str]] = []
    brief: Optional[str] = None
    level: Optional[str] = None
    file_name: Optional[str] = None  #file name of which data is filled in base_resume
    base_resume: Optional[str] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    auth_provider: Optional[str] = Field(default="custom")  # "custom" or "google"
    profile_picture: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "keshav@example.com",
                "username": "Keshav Raj",
                "phone_number": "9999999999",
                "password": "strongpassword123",
                "otp": 123456,
                "otp_expiry": "2023-10-01T12:00:00Z",
                "email_verified": False,
                "auth_provider": "custom"
            }
        }
    }


# Full User model with _id for MongoDB documents
class User(UserCreate):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},
    }
