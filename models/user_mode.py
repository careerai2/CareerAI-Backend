from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from bson import ObjectId

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
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")


# Model used for insertion
class UserCreate(BaseModel):
    email: EmailStr
    username: Optional[str]
    phone_number: Optional[str]
    password: str  # should be hashed before saving
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "email": "keshav@example.com",
                "username": "Keshav Raj",
                "phone_number": "9999999999",
                "password": "strongpassword123"
            }
        }


# Full User model with _id for MongoDB documents
class User(UserCreate):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}



