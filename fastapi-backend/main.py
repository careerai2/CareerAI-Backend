from fastapi import FastAPI, Depends,status,Request,Response,requests,responses
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from db import init_db
from routes.user_routes import router as user_router
from routes.public_routes import router as public_router
from middlewares.verify_user import auth_required as AuthMiddleware

load_dotenv()
app = FastAPI()

@app.on_event("startup")
async def on_startup():
    await init_db()



@app.get("/")
async def root():
    return {"message": "Hello World",}


app.include_router(public_router)


app.include_router(
    user_router,
    dependencies=[Depends(AuthMiddleware)],
)
