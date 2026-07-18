import pytest
from unittest.mock import patch, MagicMock
from uuid import UUID, uuid4
from datetime import datetime

# Import the module to test
from app.modules.auth import service as auth_service
from app.modules.auth.schemas import UserResponse, TokenResponse, Role


def test_hash_password():
    pw = auth_service.hash_password("secret")
    assert pw != "secret"
    assert auth_service.verify_password("secret", pw) is True
    assert auth_service.verify_password("wrong", pw) is False


def test_create_user_success():
    test_email = "test@example.com"
    test_pw = "secret123"
    mock_user_data = {
        "id": str(uuid4()),
        "email": test_email,
        "password": auth_service.hash_password(test_pw),
        "role": Role.USER.value,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }

    with patch("app.modules.auth.service.get_supabase") as mock_get_supabase:
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock(return_value=MagicMock(data=[mock_user_data]))
        mock_insert.execute = mock_execute
        mock_table.insert.return_value = mock_insert
        mock_get_supabase.return_value.table.return_value = mock_table

        result = auth_service.create_user(test_email, test_pw)

        assert result["email"] == test_email
        assert result["role"] == Role.USER.value
        assert auth_service.verify_password(test_pw, result["password"])


def test_get_user_by_email_found():
    test_email = "found@example.com"
    mock_data = [{"id": str(uuid4()), "email": test_email, "password": "hashed", "role": Role.USER.value,
                  "created_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow().isoformat()}]

    with patch("app.modules.auth.service.get_supabase") as mock_get_supabase:
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_maybe_single = MagicMock()
        mock_execute = MagicMock(return_value=MagicMock(data=mock_data[0] if mock_data else None))
        mock_maybe_single.execute = mock_execute
        mock_eq.maybe_single.return_value = mock_maybe_single
        mock_select.eq.return_value = mock_eq
        mock_table.select.return_value = mock_select
        mock_get_supabase.return_value.table.return_value = mock_table

        result = auth_service.get_user_by_email(test_email)
        assert result is not None
        assert result["email"] == test_email


def test_get_user_by_email_not_found():
    with patch("app.modules.auth.service.get_supabase") as mock_get_supabase:
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_maybe_single = MagicMock()
        mock_execute = MagicMock(return_value=MagicMock(data=None))
        mock_maybe_single.execute = mock_execute
        mock_eq.maybe_single.return_value = mock_maybe_single
        mock_select.eq.return_value = mock_eq
        mock_table.select.return_value = mock_select
        mock_get_supabase.return_value.table.return_value = mock_table

        result = auth_service.get_user_by_email("nonexist@example.com")
        assert result is None


def test_create_access_token():
    data = {"sub": "user@example.com", "role": Role.USER.value}
    token = auth_service.create_access_token(data)
    assert isinstance(token, str)
    assert len(token) > 10
    # decode and check payload
    decoded = auth_service.decode_token(token)
    assert decoded["sub"] == data["sub"]
    assert decoded["role"] == data["role"]
    assert "exp" in decoded


def test_get_current_user_valid():
    from app.modules.auth.dependencies import decode_via_token

    test_email = "user@example.com"
    test_uuid = uuid4()
    mock_user = {
        "id": str(test_uuid),
        "email": test_email,
        "role": Role.USER.value,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    token = "fake.jwt.token"

    with patch("app.modules.auth.dependencies.decode_token") as mock_decode, \
         patch("app.modules.auth.dependencies.get_user_by_email") as mock_get_user:
        mock_decode.return_value = {"sub": test_email, "role": Role.USER.value}
        mock_get_user.return_value = mock_user

        import asyncio
        result = asyncio.run(decode_via_token(token))
        assert isinstance(result, UserResponse)
        assert result.email == test_email
        assert result.id == test_uuid


def test_get_current_user_invalid_token():
    from app.modules.auth.dependencies import decode_via_token
    from fastapi import HTTPException
    from jose import JWTError

    with patch("app.modules.auth.dependencies.decode_token") as mock_decode:
        mock_decode.side_effect = JWTError("Invalid token")
        import asyncio
        with pytest.raises(HTTPException):
            asyncio.run(decode_via_token("bad.token"))