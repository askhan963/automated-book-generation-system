from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.modules.auth.dependencies import get_current_user
from app.modules.auth.schemas import (
    TokenResponse,
    UserRegisterRequest,
    UserResponse,
)
from app.modules.auth.service import (
    ACCESS_EXPIRE_MINUTES,
    create_access_token,
    create_user,
    get_user_by_email,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
)
async def register_user(payload: UserRegisterRequest):
    """Create a new user from a JSON body `{email, password}`."""
    existing = get_user_by_email(payload.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    try:
        raw_user = create_user(email=payload.email, plain_password=payload.password)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UserResponse.from_dict(raw_user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and obtain a JWT access token",
)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate with username/password and return a JWT.
    Send `application/x-www-form-urlencoded` with fields `username` (email) and `password`.
    """
    user = get_user_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    access_token = create_access_token(
        {"sub": user["email"], "role": user["role"]}
    )
    return TokenResponse(access_token=access_token, expires_in=ACCESS_EXPIRE_MINUTES)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Return the currently authenticated user",
)
async def read_current_user(current_user: UserResponse = Depends(get_current_user)):
    """Requires `Authorization: Bearer <token>`."""
    return current_user
