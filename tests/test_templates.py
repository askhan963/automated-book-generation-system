import pytest
from unittest.mock import patch, MagicMock
from uuid import UUID, uuid4
from datetime import datetime

from app.modules.templates import service as tmpl_service
from app.modules.templates.schemas import (
    TemplateCreateRequest,
    TemplateResponse,
    TemplateUpdateRequest,
    TemplateListResponse,
)


def make_template_dict(template_id=None, name="Test Template"):
    if template_id is None:
        template_id = uuid4()
    return {
        "id": str(template_id),
        "name": name,
        "description": "A test template",
        "template_json": {"chapters": [{"chapter_number": 1, "title": "Intro", "brief": "Intro"}]},
        "category": "Fiction",
        "is_public": True,
        "created_by": str(uuid4()),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


def test_create_template_success():
    payload = TemplateCreateRequest(
        name="New Template",
        description="Desc",
        template_json={"chapters": [{"chapter_number": 1, "title": "First", "brief": "First"}]},
        category="Education",
        is_public=False,
        created_by=uuid4(),
    )
    template_dict = make_template_dict(name="New Template")
    template_dict["description"] = "Desc"
    template_dict["template_json"] = {"chapters": [{"chapter_number": 1, "title": "First", "brief": "First"}]}
    template_dict["category"] = "Education"
    template_dict["is_public"] = False
    template_dict["created_by"] = str(payload.created_by)

    with patch("app.modules.templates.service.db_service") as mock_db:
        mock_db.create_template.return_value = template_dict

        resp = tmpl_service.create_template(payload)

        assert isinstance(resp, TemplateResponse)
        assert resp.name == "New Template"
        assert resp.description == "Desc"
        assert resp.category == "Education"
        assert resp.is_public is False
        assert str(resp.created_by) == str(payload.created_by)
        mock_db.create_template.assert_called_once()
        # Check passed dict
        args, _ = mock_db.create_template.call_args
        sent_data = args[0]
        assert sent_data["name"] == "New Template"
        assert sent_data["description"] == "Desc"
        assert sent_data["category"] == "Education"
        assert sent_data["is_public"] is False
        assert sent_data["created_by"] == str(payload.created_by)


def test_list_templates():
    tmpl1 = make_template_dict(uuid4(), "Template One")
    tmpl2 = make_template_dict(uuid4(), "Template Two")
    tmpl1["category"] = "Fiction"
    tmpl2["category"] = "Non-Fiction"
    with patch("app.modules.templates.service.db_service") as mock_db:
        mock_db.list_templates.return_value = [tmpl1, tmpl2]

        resp = tmpl_service.list_templates(category="Fiction", public_only=True)

        assert isinstance(resp, TemplateListResponse)
        assert len(resp.templates) == 2
        assert all(isinstance(t, TemplateResponse) for t in resp.templates)
        mock_db.list_templates.assert_called_once_with(category="Fiction", public_only=True)


def test_get_template_found():
    template_id = uuid4()
    template_dict = make_template_dict(template_id, "Found Template")
    with patch("app.modules.templates.service.db_service") as mock_db:
        mock_db.get_template.return_value = template_dict

        resp = tmpl_service.get_template(template_id)

        assert isinstance(resp, TemplateResponse)
        assert resp.id == template_id
        assert resp.name == "Found Template"
        mock_db.get_template.assert_called_once_with(template_id)


def test_get_template_not_found():
    with patch("app.modules.templates.service.db_service") as mock_db:
        mock_db.get_template.return_value = None
        with pytest.raises(Exception):  # HTTPException
            tmpl_service.get_template(uuid4())


def test_update_template_partial():
    template_id = uuid4()
    existing = make_template_dict(template_id, "Old Name")
    existing["description"] = "Old Desc"
    # Update only name and description
    payload = TemplateUpdateRequest(name="New Name", description="New Desc")
    updated = make_template_dict(template_id, "New Name")
    updated["description"] = "New Desc"
    # other fields remain same as existing
    updated["template_json"] = existing["template_json"]
    updated["category"] = existing["category"]
    updated["is_public"] = existing["is_public"]
    updated["created_by"] = existing["created_by"]

    with patch("app.modules.templates.service.db_service") as mock_db:
        mock_db.get_template.return_value = existing
        mock_db.update_template.return_value = updated

        resp = tmpl_service.update_template(template_id, payload)

        assert isinstance(resp, TemplateResponse)
        assert resp.name == "New Name"
        assert resp.description == "New Desc"
        mock_db.get_template.assert_called_once_with(template_id)
        mock_db.update_template.assert_called_once()
        args, _ = mock_db.update_template.call_args
        assert args[0] == template_id
        update_data = args[1]
        assert update_data["name"] == "New Name"
        assert update_data["description"] == "New Desc"
        # ensure other fields not present (exclude_unset)
        assert "template_json" not in update_data
        assert "category" not in update_data


def test_update_template_not_found():
    with patch("app.modules.templates.service.db_service") as mock_db:
        mock_db.get_template.return_value = None
        payload = TemplateUpdateRequest(name="New Name")
        with pytest.raises(Exception):
            tmpl_service.update_template(uuid4(), payload)


def test_delete_template_success():
    template_id = uuid4()
    with patch("app.modules.templates.service.db_service") as mock_db:
        mock_db.delete_template.return_value = True
        # Should return None (no exception)
        result = tmpl_service.delete_template(template_id)
        assert result is None
        mock_db.delete_template.assert_called_once_with(template_id)


def test_delete_template_not_found():
    with patch("app.modules.templates.service.db_service") as mock_db:
        mock_db.delete_template.return_value = False
        with pytest.raises(Exception):
            tmpl_service.delete_template(uuid4())