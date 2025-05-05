import json
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import robot

class DummyConn:
    def __init__(self, data: bytes):
        self._data = data
    def recv(self, bufsize: int) -> bytes:
        return self._data

@pytest.fixture(autouse=True)
def in_memory_db(monkeypatch):
    # patch engine & Session to use an in‑memory SQLite database
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(robot, "engine", engine)
    monkeypatch.setattr(robot, "Session", Session)
    # create all tables
    robot.Base.metadata.create_all(engine)
    yield
    # teardown happens automatically

def _make_robot_and_modules(session, module_statuses):
    """
    Helper to insert one Robot plus one Module per status in module_statuses.
    module_statuses: list of strings, e.g. ["IDLE","RUNNING","FAILED"]
    """
    # create a robot
    r = robot.Robot(
        name="TestBot",
        owner="alice",
        owner_email="alice@example.com",
        network_ssid="net",
        network_password="pw",
        ip_address="127.0.0.1",
        port=9000,
        password="pw"
    )
    session.add(r)
    session.commit()

    mods = []
    for i, st in enumerate(module_statuses, start=1):
        m = robot.Module(
            name=f"mod{i}",
            type=robot.ModuleType.VISION,
            ip_address=f"10.0.0.{i}",
            port=1000+i,
            status=robot.StatusEnum[st],
            robot_id=r.id
        )
        session.add(m)
        mods.append(m)
    session.commit()
    return r, mods

def test_handle_client_with_failed_incoming_prints_alert_and_keeps_idle(monkeypatch, capsys):
    sess = robot.Session()
    # all modules currently IDLE
    robot, mods = _make_robot_and_modules(sess, ["IDLE", "IDLE"])

    payload = {"module_id": mods[0].id, "status": "FAILED"}
    conn = DummyConn(json.dumps(payload).encode())

    before = datetime.now(timezone.utc)
    robot.handle_client(conn, robot.id)
    after = datetime.now(timezone.utc)

    # reload robot
    sess2 = robot.Session()
    updated = sess2.query(robot.Robot).get(robot.id)

    # since DB modules are both IDLE, robot.status stays IDLE
    assert updated.status == robot.StatusEnum.IDLE

    # last_online should be updated to a timestamp between before/after
    assert before <= updated.last_online <= after

    out = capsys.readouterr().out
    # only prints when incoming_status is FAILED
    assert "STATUS: FAILED" in out
    assert mods[0].id in out

def test_handle_client_running_updates_to_running_without_alert(capsys):
    sess = robot.Session()
    # one module IDLE, one RUNNING
    robot, mods = _make_robot_and_modules(sess, ["IDLE", "RUNNING"])

    payload = {"module_id": mods[0].id, "status": "IDLE"}  # incoming IDLE
    conn = DummyConn(json.dumps(payload).encode())

    robot.handle_client(conn, robot.id)

    sess2 = robot.Session()
    updated = sess2.query(robot.Robot).get(robot.id)

    # because one module is RUNNING in the DB, robot.status → RUNNING
    assert updated.status == robot.StatusEnum.RUNNING

    out = capsys.readouterr().out
    # no alert printed, as incoming_status != FAILED
    assert out == ""

def test_handle_client_failed_in_db_updates_to_failed_without_alert(capsys):
    sess = robot.Session()
    # one module FAILED in DB, one IDLE
    robot, mods = _make_robot_and_modules(sess, ["FAILED", "IDLE"])

    payload = {"module_id": mods[1].id, "status": "RUNNING"}  # incoming RUNNING
    conn = DummyConn(json.dumps(payload).encode())

    robot.handle_client(conn, robot.id)

    sess2 = robot.Session()
    updated = sess2.query(robot.Robot).get(robot.id)

    # because a module is FAILED in the DB, robot.status → FAILED
    assert updated.status == robot.StatusEnum.FAILED

    out = capsys.readouterr().out
    # still no alert, since incoming_status != FAILED
    assert out == ""
