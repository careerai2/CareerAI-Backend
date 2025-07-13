import jwt
from datetime import datetime, timedelta

# 🔐 Your secret configuration
SECRET_KEY = 'your-secret-key'
ALGORITHM = 'HS256'
EXPIRATION_MINUTES = 60

# ✅ JWT creation
def create_jwt(user_id: int, role: str) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=EXPIRATION_MINUTES),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

# ✅ JWT decoding
def decode_jwt(token: str) -> dict | None:
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return decoded
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
