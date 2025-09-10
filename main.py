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
from postgress_db import get_postgress_db
from assistant.resume.chat.swarm import stream_graph_to_websocket,update_resume
from app_instance import app
from bson import ObjectId
import logging
from assistant.resume.chat.utils.common_tools import get_tailoring_keys 
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.sessions import SessionMiddleware

import assistant.resume.chat.token_count as token_count

# Configure logging
logging.basicConfig(level=logging.INFO)



app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://localhost:5174"],  # Replace "*" with your frontend URL for better security
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

app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "supersecretkey"))

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
async def resume_chat_ws(websocket: WebSocket, resume_id: str, postgresql_db: AsyncSession = Depends(get_postgress_db)):
    db = get_database()
    user = await websocket_auth(websocket, db)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    resume = await db["resumes"].find_one({"_id": ObjectId(resume_id), "user_id": user["_id"]})
    if not resume:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # await app.state.connection_manager.connect(websocket)
    user_id = await app.state.connection_manager.connect(websocket)
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    tailoring_keys = get_tailoring_keys(str(user["_id"]), resume_id) or resume.get("tailoring_keys", [])
    # print(f"User {user['_id']} connected to resume {resume_id} with tailoring keys: {tailoring_keys}")
    try:
        while True:
            user_input = await websocket.receive_json()

            if user_input["type"] == "save_resume":
                thread_id = f"{user['_id']}:{resume_id}"
                await update_resume(thread_id, user_input["resume"])
                print("LLM Resume state updated")
                # await websocket.send_json({"type": "system", "message": "Resume updated in agent state"})

            elif user_input["type"] == "chat":
                await stream_graph_to_websocket(
                    user_input=user_input["message"],
                    websocket=websocket,
                    user_id=str(user["_id"]),
                    resume_id=resume_id,
                    tailoring_keys=tailoring_keys,
                    db=postgresql_db
                )
                
                
                print("Total Input Tokens:", token_count.total_Input_Tokens)
                print("Total Output Tokens:", token_count.total_Output_Tokens)
    except WebSocketDisconnect:
        print(f"User {user['_id']} disconnected")
        app.state.connection_manager.disconnect(user_id)
        print(f"User {user_id} disconnected")
        # app.state.connection_manager.active_connections.pop(user["_id"], None)
