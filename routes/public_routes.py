from fastapi import APIRouter,HTTPException,Depends,Request,Query
from controllers.user_controller import signup_user,login_user,google_auth,verify_otp
from validation.user_types import UserSignup, UserLogin,GoogleAuth_Input,OtpVerification
from db import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi.responses import RedirectResponse
from starlette.config import Config
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.ext.asyncio import AsyncSession
from middlewares.verify_user import auth_required
from utils.verify_token import verify_token
from controllers.user_controller import quick_save_resume
import jwt
import json
router = APIRouter(prefix="/api/auth", tags=["users"])



@router.post("/signup")
async def create_user(user_data: UserSignup, db: AsyncIOMotorDatabase = Depends(get_database)):
    try:
        print("Received user data for signup:", user_data)
        return await signup_user(user_data, db)
    except Exception as e:
        print(f"Error during user signup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-otp")
async def check_otp(otp_data: OtpVerification, db: AsyncIOMotorDatabase = Depends(get_database)):
    try:
        print("Received OTP verification data:", otp_data)
        return await verify_otp(otp_data, db)
    except Exception as e:
        print(f"Error during OTP verification: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/login")
async def userLogin(user_data: UserLogin, db: AsyncIOMotorDatabase = Depends(get_database)):
    try:
        return await login_user(user_data, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
SECRET_KEY = 'your-secret-key'
@router.post("/resume/quick-save/{resume_id}")
async def quick_save_resume_beacon(
    resume_id: str,
    request: Request,
    db: AsyncSession = Depends(get_database),
    delCache: bool = Query(False, description="Delete cache flag"),
):
    print("Quick save beacon hit for resume_id:", resume_id)
    try:
        
        # read raw payload
        body = await request.body()
        if not body:
            return {"ok": True}  # silent success for beacon

        payload = json.loads(body.decode("utf-8"))

        token = payload.get("token")
        resume_data = payload.get("data")

        if not token or not resume_data:
            return {"ok": True}  # silent success

        # decode token (no DB!)
        try:
            user = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except:
            return {"ok": True}

        user_id = user.get("_id")
        if not user_id:
            return {"ok": True}

        # very fast DB write (UPSERT)
        await quick_save_resume(
            resume_id,
            user_id,
            resume_data,
            db,
            delCache
        )

        return {"ok": True}  # always ok

    except Exception as e:
        # do NOT raise exceptions in a beacon handler
        return {"ok": True}

    
# config = Config(".env")
# oauth = OAuth(config)
# oauth.register(
#     name="google",
#     client_id=config("GOOGLE_CLIENT_ID"),
#     client_secret=config("GOOGLE_CLIENT_SECRET"),
#     server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
#     client_kwargs={"scope": "openid email profile"},
# )


# @router.get("/google-login")
# async def login(request:Request):
#     redirect_uri = request.url_for("google_auth")
#     return await oauth.google.authorize_redirect(request, redirect_uri)

# @router.get("/google-auth", name="google_auth")
# async def auth(request:Request,db: AsyncIOMotorDatabase = Depends(get_database)):
#     token = await oauth.google.authorize_access_token(request)
#     user = await oauth.google.userinfo(token=token)
#     user_data = GoogleAuth_Input(
#         email=user["email"],
#         name=user.get("name"),
#         picture=user.get("picture"),
#         email_verified=user.get("email_verified", False)
#     )
#     print("User authenticated:", token)
#     return google_auth(user_data, db)