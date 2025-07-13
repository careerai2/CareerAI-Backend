from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from models.user_model import User
from utils.jwt import decode_jwt
from db import get_session

async def auth_required(
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth_header.split(" ")[1]
    payload = decode_jwt(token)

    if not payload:
        raise HTTPException(status_code=403, detail="Token invalid or expired")

    result = await session.exec(select(User).where(User.id == payload["user_id"]))
    user = result.one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    request.state.user = user  # Optional: store for later use
    return user
