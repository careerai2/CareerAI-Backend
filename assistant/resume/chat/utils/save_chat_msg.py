from sqlalchemy.ext.asyncio import AsyncSession
from models.chat_msg_model import ChatMessage  # Adjust import according to your file structure
from typing import Literal

async def save_chat_message(
    db: AsyncSession, 
    user_id: str, 
    resume_id: str,
    message: str, 
    type: Literal['received', 'sent'] = "received", 
    sender: Literal['bot','user']= "user"  # default to 'user'
) -> ChatMessage:
    chat_msg = ChatMessage(
        user_id=user_id,
        resume_id=resume_id,
        type=type,
        text=message,
        sender=sender
    )
    db.add(chat_msg)
    await db.commit()
    await db.refresh(chat_msg)
    return chat_msg
