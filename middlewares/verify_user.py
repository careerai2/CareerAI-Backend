from fastapi import Request, Depends, HTTPException, WebSocket, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from utils.jwt import decode_jwt
from config.db import get_database  # Dependency that returns `AsyncIOMotorDatabase`


async def auth_required(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = auth_header.split(" ")[1]
    payload = decode_jwt(token)

    if not payload or "user_id" not in payload:
        raise HTTPException(status_code=403, detail="Token invalid or expired")

    user = await db["users"].find_one({"_id": ObjectId(payload["user_id"])})

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # print(f"Authenticated user: {user}")
    
    request.state.user = user  # Optional: store for later use
    return user


async def websocket_auth(websocket: WebSocket, db: AsyncIOMotorDatabase = Depends(get_database)):
    # Extract token from query parameters
    token = websocket.query_params.get("token")
    print(f"WebSocket token: {token}")

    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    payload = decode_jwt(token)
    if not payload or "user_id" not in payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    user = await db["users"].find_one({"_id": ObjectId(payload["user_id"])})

    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return None

    return user
