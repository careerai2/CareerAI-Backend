from fastapi import FastAPI, Depends,Request,status
from fastapi.responses import JSONResponse
from db import init_db
from routes.user_routes import router as user_router
from routes.public_routes import router as public_router
from middlewares.verify_user import auth_required as AuthMiddleware
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv

app = FastAPI()

load_dotenv()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
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


app.include_router(user_router,dependencies=[Depends(AuthMiddleware)])
