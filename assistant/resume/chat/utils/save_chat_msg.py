from sqlalchemy.ext.asyncio import AsyncSession
from models.chat_msg_model import ChatMessage  # Adjust import according to your file structure

async def save_chat_message(
    db: AsyncSession, 
    user_id: str, 
    resume_id: str, 
    message: str, 
    sender_role: str = "user"  # default to 'user'
) -> ChatMessage:
    chat_msg = ChatMessage(
        user_id=user_id,
        resume_id=resume_id,
        message=message,
        sender_role=sender_role
    )
    db.add(chat_msg)
    await db.commit()
    await db.refresh(chat_msg)
    return chat_msg
