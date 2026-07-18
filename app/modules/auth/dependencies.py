"""Auth dependency injection for FastAPI routes."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from app.modules.auth.schemas import Role, UserResponse
from app.modules.auth.service import decode_token, get_user_by_email

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


async def decode_via_token(token: str) -> UserResponse:
    """Decode a raw JWT string into a UserResponse."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise credentials_exception from exc

    email = payload.get("sub")
    if not email:
        raise credentials_exception

    user = get_user_by_email(email)
    if user is None:
        raise credentials_exception

    return UserResponse.from_dict(user)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserResponse:
    """Resolve the authenticated user from a Bearer JWT."""
    return await decode_via_token(token)


async def get_current_admin(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Require an admin role."""
    if current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
