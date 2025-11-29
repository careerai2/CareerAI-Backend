from sqlalchemy import Column, Integer, String, DateTime, func, Enum
from config.postgress_db import Base

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    resume_id = Column(String, index=True)
    text = Column(String)
    type = Column(Enum('received', 'sent', name='message_type'), nullable=False)
    sender = Column(Enum('user', 'bot', name='sender'), nullable=False, default='user')
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
