from typing import Dict
from fastapi import WebSocket
from bson import ObjectId
from middlewares.verify_user import websocket_auth
from db import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}  # user_id (str) -> WebSocket

    async def connect(self, websocket: WebSocket):
        db: AsyncIOMotorDatabase = get_database()
        user = await websocket_auth(websocket, db)  # This returns a MongoDB user doc

        if not user:
            return None

        await websocket.accept()
        user_id = str(user["_id"])  # MongoDB _id is ObjectId, convert to str
        self.active_connections[user_id] = websocket
        print(f"WebSocket connection established for user {user_id}")
        return user_id

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)

    async def send_to_user(self, user_id: str, message: str):
        websocket = self.active_connections.get(user_id)
        if websocket:
            await websocket.send_text(message)

    async def send_json_to_user(self, user_id: str, message: dict):
        websocket = self.active_connections.get(user_id)
        if websocket:
            # print(f"Sending JSON to user {user_id}: {message}")
            await websocket.send_json(message)

    async def broadcast(self, message: str):
        for ws in self.active_connections.values():
            await ws.send_text(message)
