import pytest
from unittest.mock import patch, MagicMock
from uuid import UUID, uuid4
from datetime import datetime

from app.modules.projects import service as proj_service
from app.modules.projects.service import (
    create_project,
    get_project,
    list_projects_by_user,
    update_project,
    delete_project,
    create_api_key,
)
from app.modules.auth.schemas import Role, UserResponse


def make_mock_project(project_id=None, name="Test Project", owner_id=None):
    if project_id is None:
        project_id = uuid4()
    if owner_id is None:
        owner_id = uuid4()
    return {
        "id": str(project_id),
        "name": name,
        "description": None,
        "owner_id": str(owner_id),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


def test_create_project():
    name = "New Project"
    description = "A test project"
    owner_id = uuid4()
    mock_proj = make_mock_project(name=name, owner_id=owner_id)
    mock_proj["description"] = description

    with patch("app.modules.projects.service.get_supabase") as mock_get_sb, \
         patch("app.modules.projects.service._run") as mock_run:
        mock_table = MagicMock()
        mock_upsert = MagicMock()
        mock_execute = MagicMock(return_value=MagicMock(data=[mock_proj]))
        mock_upsert.execute = mock_execute
        mock_table.upsert.return_value = mock_upsert
        mock_get_sb.return_value.table.return_value = mock_table
        # _run just calls the passed lambda
        mock_run.side_effect = lambda func: func()

        result = proj_service.create_project(name, description, owner_id)

        assert result["id"] == str(mock_proj["id"])
        assert result["name"] == name
        assert result["description"] == description
        assert result["owner_id"] == str(owner_id)
        mock_table.upsert.assert_called_once()
        # check payload passed to upsert
        args, kwargs = mock_table.upsert.call_args
        payload = args[0]
        assert payload["name"] == name
        assert payload["description"] == description
        assert payload["owner_id"] == str(owner_id)
        assert "updated_at" in payload


def test_get_project_found():
    project_id = uuid4()
    mock_proj = make_mock_project(project_id)

    with patch("app.modules.projects.service.get_supabase") as mock_get_sb, \
         patch("app.modules.projects.service._run") as mock_run:
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_maybe_single = MagicMock()
        mock_execute = MagicMock(return_value=MagicMock(data=mock_proj))
        mock_maybe_single.execute = mock_execute
        # chain
        eq_maybe_single = mock_eq.maybe_single.return_value
        select_eq = mock_select.eq.return_value
        table_select = mock_table.select.return_value
        mock_eq.maybe_single.return_value = mock_maybe_single
        mock_select.eq.return_value = mock_eq
        mock_table.select.return_value = mock_select
        mock_get_sb.return_value.table.return_value = mock_table
        mock_run.side_effect = lambda func: func()

        result = proj_service.get_project(project_id)

        assert result is not None
        assert result["id"] == str(project_id)
        assert result["name"] == "Test Project"
        mock_table.select.assert_called_once_with("*")
        mock_select.eq.assert_called_once_with("id", str(project_id))


def test_get_project_not_found():
    with patch("app.modules.projects.service.get_supabase") as mock_get_sb, \
         patch("app.modules.projects.service._run") as mock_run:
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_maybe_single = MagicMock()
        mock_execute = MagicMock(return_value=MagicMock(data=None))
        mock_maybe_single.execute = mock_execute
        # When data is None, maybe_single returns None?
        mock_eq.maybe_single.return_value = mock_maybe_single
        mock_select.eq.return_value = mock_eq
        mock_table.select.return_value = mock_select
        mock_get_sb.return_value.table.return_value = mock_table
        mock_run.side_effect = lambda func: func()

        result = proj_service.get_project(uuid4())
        assert result is None


def test_list_projects_by_user():
    user_id = uuid4()
    proj1 = make_mock_project(uuid4(), "Project A", user_id)
    proj2 = make_mock_project(uuid4(), "Project B", user_id)

    with patch("app.modules.projects.service.get_supabase") as mock_get_sb, \
         patch("app.modules.projects.service._run") as mock_run:
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_execute = MagicMock(return_value=MagicMock(data=[proj1, proj2]))
        mock_eq.execute = mock_execute
        mock_select.eq.return_value = mock_eq
        mock_table.select.return_value = mock_select
        mock_get_sb.return_value.table.return_value = mock_table
        mock_run.side_effect = lambda func: func()

        result = proj_service.list_projects_by_user(user_id)

        assert len(result) == 2
        assert all(p["owner_id"] == str(user_id) for p in result)
        mock_table.select.assert_called_once_with("*")
        mock_select.eq.assert_called_once_with("owner_id", str(user_id))


def test_update_project():
    project_id = uuid4()
    original = make_mock_project(project_id, "Old Name", "Old Desc")
    updated = dict(original)
    updated["name"] = "New Name"
    updated["description"] = "New Description"
    updated["updated_at"] = datetime.utcnow().isoformat()

    with patch("app.modules.projects.service.get_supabase") as mock_get_sb, \
         patch("app.modules.projects.service._run") as mock_run:
        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_eq = MagicMock()
        mock_execute = MagicMock(return_value=MagicMock(data=[updated]))
        mock_eq.execute = mock_execute
        mock_update.eq.return_value = mock_eq
        mock_table.update.return_value = mock_update
        mock_get_sb.return_value.table.return_value = mock_table
        mock_run.side_effect = lambda func: func()

        result = proj_service.update_project(project_id, name="New Name", description="New Description")

        assert result is not None
        assert result["name"] == "New Name"
        assert result["description"] == "New Description"
        mock_table.update.assert_called_once()
        args, _ = mock_table.update.call_args
        payload = args[0]
        assert payload["name"] == "New Name"
        assert payload["description"] == "New Description"
        assert "updated_at" in payload
        mock_update.eq.assert_called_once_with("id", str(project_id))


def test_delete_project():
    project_id = uuid4()

    with patch("app.modules.projects.service.get_supabase") as mock_get_sb, \
         patch("app.modules.projects.service._run") as mock_run:
        mock_table = MagicMock()
        mock_delete = MagicMock()
        mock_eq = MagicMock()
        mock_execute = MagicMock(return_value=MagicMock())
        mock_eq.execute = mock_execute
        mock_delete.eq.return_value = mock_eq
        mock_table.delete.return_value = mock_delete
        mock_get_sb.return_value.table.return_value = mock_table
        mock_run.side_effect = lambda func: func()

        # Should not raise
        proj_service.delete_project(project_id)

        mock_table.delete.assert_called_once()
        mock_delete.eq.assert_called_once_with("id", str(project_id))


def test_create_api_key():
    project_id = uuid4()
    raw_key = "mysecretkey123"
    key_id = uuid4()
    key_hash = "hashedvalue"
    expires_at = None

    with patch("app.modules.projects.service.get_supabase") as mock_get_sb, \
         patch("app.modules.projects.service._run") as mock_run, \
         patch("hashlib.sha256") as mock_sha256:
        mock_sha256.return_value.hexdigest.return_value = key_hash
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock(return_value=MagicMock(data=[{
            "id": str(key_id),
            "project_id": str(project_id),
            "key_hash": key_hash,
            "expires_at": None,
            "revoked": False,
            "created_at": datetime.utcnow().isoformat(),
        }]))
        mock_insert.execute = mock_execute
        mock_table.insert.return_value = mock_insert
        mock_get_sb.return_value.table.return_value = mock_table
        mock_run.side_effect = lambda func: func()

        result = proj_service.create_api_key(project_id, raw_key, expires_at)

        assert result["project_id"] == str(project_id)
        assert result["key_hash"] == key_hash
        # Should have called insert with proper payload
        mock_table.insert.assert_called_once()
        args, _ = mock_table.insert.call_args
        payload = args[0]
        assert payload["project_id"] == str(project_id)
        assert payload["key_hash"] == key_hash
        assert payload["revoked"] is False
        assert payload["expires_at"] is None
