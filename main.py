from fastapi import FastAPI, Depends,Request, WebSocketDisconnect,status,websockets,WebSocket
from fastapi.responses import JSONResponse
from websocket_manger import ConnectionManager
from db import init_db
from routes.user_routes import router as user_router
from routes.public_routes import router as public_router
from middlewares.verify_user import auth_required as AuthMiddleware,websocket_auth
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Annotated
import os
from db import get_database
from assistant.resume.chat.graph import stream_graph_to_websocket
from app_instance import app
from bson import ObjectId


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with your frontend URL for better security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# load_dotenv()
os.environ["OPENAI_API_KEY"]=os.getenv("OPENAI_API_KEY")
os.environ["GOOGLE_API_KEY"]=os.getenv("GOOGLE_API_KEY")

## Langmith tracking
os.environ["LANGCHAIN_TRACING_V2"]="true"
os.environ["LANGCHAIN_API_KEY"]=os.getenv("LANGCHAIN_API_KEY")

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"Validation error: {exc}")
    print(f"Request body: {await request.body()}")
    return JSONResponse(
        status_code=status.HTTP_406_NOT_ACCEPTABLE,
        content={"message": "Invalid input", "details": exc.errors()},
    )

@app.on_event("startup")
async def on_startup():
    await init_db()
    



@app.get("/")
async def root():
    return {"message": "Hello World",}


app.include_router(public_router)



# User Authentication required for user routes
app.include_router(user_router,dependencies=[Depends(AuthMiddleware)])




@app.websocket("/resume-chat-ws/{resume_id}")
async def resume_chat_ws(websocket: WebSocket, resume_id: str):
    
    print(f"WebSocket connection request for resume {resume_id}")
    db = get_database()
    user = await websocket_auth(websocket, db)

    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Verify resume_id belongs to this user
    resume = await db["resumes"].find_one({"_id": ObjectId(resume_id), "user_id": user["_id"]})
    if not resume:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    print(f"User {user['_id']} connected to resume {resume_id}")
    manager = app.state.connection_manager
    await manager.connect(websocket)

    try:
        while True:
            user_input = await websocket.receive_text()
            await stream_graph_to_websocket(
                user_input=user_input,
                websocket=websocket,
                user_id=user["_id"],
                resume_id=resume_id
            )
    except WebSocketDisconnect:
        print(f"User {user['_id']} disconnected")
    finally:
        manager.active_connections.pop(user["_id"], None)
