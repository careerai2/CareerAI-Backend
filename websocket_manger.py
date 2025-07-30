from typing import Dict
from fastapi import WebSocket
from middlewares.verify_user import websocket_auth
from db import get_session

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}  # user_id -> WebSocket

    async def connect(self, websocket: WebSocket):
        session = await get_session().__anext__()  # good if you're using async generator from a dependency override
        user = await websocket_auth(websocket, session)  # custom middleware that returns authenticated user

        await websocket.accept()
        self.active_connections[str(user.id)] = websocket
        print(f"WebSocket connection established for user {user.id}")
        return user.id

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)

    async def send_to_user(self, user_id: str, message: str):
        websocket = self.active_connections.get(user_id)
        if websocket:
            await websocket.send_text(message)
            
    async def send_json_to_user(self, user_id: str, message: dict):
        websocket = self.active_connections.get(user_id)
        if websocket:
            print(f"Sending JSON to user {user_id}: {message}")
            await websocket.send_json(message)

    async def broadcast(self, message: str):
        for ws in self.active_connections.values():
            await ws.send_text(message)
