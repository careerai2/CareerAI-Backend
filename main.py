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
from db import get_session
from assistant.resume.chat.graph import stream_graph_to_websocket
from app_instance import app

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


# For chatting with the resume extraction model
@app.websocket("/resume-chat-ws")
async def resume_chat_ws(websocket: WebSocket):
    session = await get_session().__anext__()  # assumes this yields session
    user = await websocket_auth(websocket, session)

    if not user:
        print("User not authenticated")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # await websocket.accept()
    print(f"User {user.id} connected")
    manager = app.state.connection_manager
    await manager.connect(websocket)

    try:
        while True:
            user_input = await websocket.receive_text()
            print(f"User {user.id} sent: {user_input}")

            # Stream response from LangGraph
            await stream_graph_to_websocket(
                user_input=user_input,
                thread_id=user.id,
                websocket=websocket,
                user_id=user.id
            )

    except WebSocketDisconnect:
        print(f"User {user.id} disconnected")

    finally:
        # Cleanup connection from manager
        manager.active_connections.pop(user.id, None)