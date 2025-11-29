from fastapi import Request, Depends, HTTPException, WebSocket, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from utils.jwt import decode_jwt
from config.db import get_database  # Dependency that returns `AsyncIOMotorDatabase`


async def verify_token(token: str, db: AsyncIOMotorDatabase):
   
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    payload = decode_jwt(token)

    if not payload or "user_id" not in payload:
        raise HTTPException(status_code=403, detail="Token invalid or expired")

    user = await db["users"].find_one({"_id": ObjectId(payload["user_id"])})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # print(f"Authenticated user: {user}")
    
    return user

