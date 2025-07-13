from sqlmodel import SQLModel
from pydantic import BaseModel
from typing import Optional

class UserCreate(SQLModel):
    username: str
    phone: Optional[int]
    password: str
    intro: Optional[str] = ""



class UserLogin(BaseModel):
    username: str
    password: str