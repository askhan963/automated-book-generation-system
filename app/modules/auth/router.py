from fastapi import APIRouter, Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordRequestForm
from uuid import UUID

from app.modules.auth.schemas import UserResponse, TokenResponse
from app.modules.auth.service import (
    create_user,
    get_user_by_email,
    verify_password,
    create_access_token,
    get_current_user,
    ACCESS_EXPIRE_MINUTES,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# ----------------------------------------------------------------------
#  Register
# ----------------------------------------------------------------------
@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user account",
)
async def register_user(email: str, password: str):
    """Create a new user."""
    try:
        # Call service layer to create user
        raw_user = create_user(email=email, plain_password=password)
    except Exception as exc:
        # Propagate DB or validation errors as 400 responses
        raise HTTPException(status_code=400, detail=str(exc))
    # Return the user payload (no password hash)
    return UserResponse.from_dict(raw_user)


# ----------------------------------------------------------------------
#  Login – OAuth2 password flow
# ----------------------------------------------------------------------
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and obtain a JWT access token",
)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate with username/password and return a JWT.
    FastAPI's OAuth2PasswordRequestForm expects fields `username` and `password`.
    """
    # Find user by the username (email) and verify password
    user = get_user_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    # Generate JWT (sub = email, role = user.role)
    access_token = create_access_token(
        {"sub": user["email"], "role": user["role"]}
    )

    return TokenResponse(access_token=access_token, expires_in=ACCESS_EXPIRE_MINUTES)


# ----------------------------------------------------------------------
#  Me – protected endpoint that returns current user
# ----------------------------------------------------------------------
@router.get(
    "/me",
    response_model=UserResponse,
    summary="Return the currently authenticated user",
)
async def read_current_user(current_user: UserResponse = Depends(get_current_user)):
    """
    Returns the user object (id, email, role, timestamps).  Requires a valid
    Bearer JWT token in the Authorization header.
    """
    return current_user