from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError
import os

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


# ✅ move these to .env in production
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_ME_SECRET")
JWT_REFRESH_SECRET_KEY = os.getenv("JWT_REFRESH_SECRET_KEY", "CHANGE_ME_REFRESH_SECRET")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(subject: str, role: str):
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "role": role,
        "type": "access",
        "exp": expire
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(subject: str):
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": subject,
        "type": "refresh",
        "exp": expire
    }
    return jwt.encode(payload, JWT_REFRESH_SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str):
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def decode_refresh_token(token: str):
    try:
        return jwt.decode(token, JWT_REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
