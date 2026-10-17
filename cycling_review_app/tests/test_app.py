import os
import tempfile

import pytest


@pytest.fixture()
def client():
    from app import create_app

    database_fd, database_path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(database_fd)

    app = create_app(
        {
            "TESTING": True,
            "DATABASE": database_path,
        }
    )

    with app.test_client() as test_client:
        yield test_client

    os.unlink(database_path)


def valid_record_form(**overrides):
    form = {
        "ride_date": "2026-10-16",
        "distance_km": "42.5",
        "duration_minutes": "120",
        "average_speed": "21.25",
        "average_heart_rate": "145",
        "max_heart_rate": "176",
        "elevation_gain": "380",
        "fatigue": "7",
        "notes": "沿江骑行，后半程有逆风。",
    }
    form.update(overrides)
    return form


def valid_plan_form(**overrides):
    form = {
        "goal": "endurance",
        "weeks": "4",
        "rides_per_week": "3",
        "start_date": "2026-10-19",
    }
    form.update(overrides)
    return form


def test_homepage_shows_empty_state(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "还没有骑行记录" in response.get_data(as_text=True)


def test_create_and_view_record(client):
    response = client.post("/records/new", data=valid_record_form(), follow_redirects=True)

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "骑行记录已保存" in body
    assert "42.5" in body
    assert "沿江骑行" in body


def test_invalid_record_is_rejected(client):
    response = client.post(
        "/records/new",
        data=valid_record_form(distance_km="-1", fatigue="11"),
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "距离必须大于 0" in body
    assert "疲劳程度必须是 1 到 10 分" in body


def test_edit_record_updates_saved_values(client):
    create_response = client.post("/records/new", data=valid_record_form())
    record_id = create_response.headers["Location"].rstrip("/").split("/")[-1]

    response = client.post(
        f"/records/{record_id}/edit",
        data=valid_record_form(distance_km="50", notes="已完成编辑"),
        follow_redirects=True,
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "骑行记录已更新" in body
    assert ">50 <" in body
    assert "已完成编辑" in body


def test_delete_record_removes_it_from_list(client):
    create_response = client.post("/records/new", data=valid_record_form())
    record_id = create_response.headers["Location"].rstrip("/").split("/")[-1]

    response = client.post(f"/records/{record_id}/delete", follow_redirects=True)

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "骑行记录已删除" in body
    assert "还没有骑行记录" in body


def test_records_persist_when_app_is_recreated(tmp_path):
    from app import create_app

    database_path = tmp_path / "persistent.sqlite3"
    config = {"TESTING": True, "DATABASE": str(database_path)}

    first_app = create_app(config)
    with first_app.test_client() as first_client:
        first_client.post("/records/new", data=valid_record_form())

    second_app = create_app(config)
    with second_app.test_client() as second_client:
        response = second_client.get("/")

    assert response.status_code == 200
    assert "42.5" in response.get_data(as_text=True)


def test_create_training_plan_from_history_and_update_session(client):
    from db import get_training_sessions

    client.post("/records/new", data=valid_record_form())
    response = client.post("/plans/new", data=valid_plan_form())

    assert response.status_code == 302
    plan_id = int(response.headers["Location"].rstrip("/").split("/")[-1])

    detail_response = client.get(f"/plans/{plan_id}")
    detail_body = detail_response.get_data(as_text=True)
    assert detail_response.status_code == 200
    assert "训练计划" in detail_body
    assert "第 1 周" in detail_body
    assert "轻松骑" in detail_body

    with client.application.app_context():
        session = get_training_sessions(plan_id)[0]

    update_response = client.post(
        f"/plans/{plan_id}/sessions/{session['id']}/update",
        data={"target_distance_km": "18.5", "completed": "1"},
        follow_redirects=True,
    )

    update_body = update_response.get_data(as_text=True)
    assert update_response.status_code == 200
    assert "训练日已更新" in update_body
    assert "18.5" in update_body
    assert "已完成" in update_body


def test_training_plan_rejects_non_positive_session_distance(client):
    client.post("/records/new", data=valid_record_form())
    response = client.post("/plans/new", data=valid_plan_form())
    plan_id = int(response.headers["Location"].rstrip("/").split("/")[-1])

    from db import get_training_sessions

    with client.application.app_context():
        session = get_training_sessions(plan_id)[0]

    update_response = client.post(
        f"/plans/{plan_id}/sessions/{session['id']}/update",
        data={"target_distance_km": "0"},
    )

    assert update_response.status_code == 400
    assert "训练距离必须大于 0" in update_response.get_data(as_text=True)


def test_training_plan_persists_when_app_is_recreated(tmp_path):
    from app import create_app

    database_path = tmp_path / "training-plan.sqlite3"
    config = {"TESTING": True, "DATABASE": str(database_path)}

    first_app = create_app(config)
    with first_app.test_client() as first_client:
        first_client.post("/records/new", data=valid_record_form())
        plan_response = first_client.post("/plans/new", data=valid_plan_form())
        plan_id = int(plan_response.headers["Location"].rstrip("/").split("/")[-1])

    second_app = create_app(config)
    with second_app.test_client() as second_client:
        response = second_client.get(f"/plans/{plan_id}")

    assert response.status_code == 200
    assert "提升耐力" in response.get_data(as_text=True)

