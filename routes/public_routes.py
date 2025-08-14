from fastapi import APIRouter,HTTPException,Depends,Request
from controllers.user_controller import signup_user,login_user,google_auth,verify_otp
from validation.user_types import UserSignup, UserLogin,GoogleAuth_Input,OtpVerification
from db import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi.responses import RedirectResponse
from starlette.config import Config
from authlib.integrations.starlette_client import OAuth



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
    token = await oauth.google.authorize_access_token(request)
    user = await oauth.google.userinfo(token=token)
    user_data = GoogleAuth_Input(
        email=user["email"],
        name=user.get("name"),
        picture=user.get("picture"),
        email_verified=user.get("email_verified", False)
    )
    print("User authenticated:", token)
    return google_auth(user_data, db)