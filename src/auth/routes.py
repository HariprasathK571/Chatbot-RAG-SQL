from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select


from src.db.core import get_session
from src.auth.models import User
from src.auth.schema import RegisterRequest, LoginRequest, TokenResponse, UserResponse, RefreshRequest
from src.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_refresh_token
)
from src.auth.deps import get_current_user
from fastapi.security import OAuth2PasswordRequestForm


auth_router = APIRouter()


@auth_router.post("/register", response_model=UserResponse)
async def register(req: RegisterRequest, session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(User).where(User.email == req.email))
    existing = result.one_or_none()  # ✅ changed

    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        full_name=req.full_name,
        email=req.email,
        hashed_password=hash_password(req.password),
        role="user"
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return UserResponse(
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active
    )


@auth_router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    email = form_data.username
    password = form_data.password

    result = await session.exec(select(User).where(User.email == email))
    user = result.one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is disabled")

    access_token = create_access_token(subject=user.email, role=user.role)
    refresh_token = create_refresh_token(subject=user.email)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)




@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh_token(req: RefreshRequest, session: AsyncSession = Depends(get_session)):
    payload = decode_refresh_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    email = payload.get("sub")
    result = await session.exec(select(User).where(User.email == email))
    user = result.one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid user")

    new_access = create_access_token(subject=user.email, role=user.role)
    new_refresh = create_refresh_token(subject=user.email)

    return TokenResponse(access_token=new_access, refresh_token=new_refresh)




@auth_router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return UserResponse(
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active
    )
