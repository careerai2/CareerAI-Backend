from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime




# ✅ DB Model
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(max_length=120, unique=True)
    phone: Optional[int] = Field(default=None)
    password: str = Field(max_length=128)
    intro: str = Field(default="", max_length=500)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
 
    
    
class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    title: str
    description: Optional[str] = None
    completed: bool = Field(default=False)
    
    created_at: datetime = Field(default_factory=datetime.utcnow())
    updated_at: datetime = Field(default_factory=datetime.utcnow(), sa_column_kwargs={"onupdate": datetime.utcnow})
