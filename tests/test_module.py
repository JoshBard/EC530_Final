import sys
import uuid
import json
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, clear_mappers

import module

class DummyConn:
    def __init__(self, data: bytes):
        self._data = data
    def recv(self, bufsize: int) -> bytes:
        return self._data

class FakeSocket:
    def __init__(self):
        self.connected_to = None
        self.sent_data = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass

    def connect(self, addr):
        self.connected_to = addr

    def sendall(self, data):
        self.sent_data = data

@pytest.fixture(autouse=True)
def in_memory_db(monkeypatch):
    """Patch module.engine & Session to use in-memory SQLite and recreate tables."""
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=eng)
    monkeypatch.setattr(module, "engine", eng)
    monkeypatch.setattr(module, "Session", Session)
    module.Base.metadata.create_all(eng)
    yield

def test_usage_no_args(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["prog"])
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Usage:" in out

def test_missing_module(monkeypatch, capsys):
    fake_id = str(uuid.uuid4())
    monkeypatch.setattr(sys, "argv", ["prog", fake_id])
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert f"ERROR: module {fake_id} not found." in out

def test_missing_robot(monkeypatch, capsys):
    # insert one module with robot_id that doesn't exist
    sess = module.Session()
    mid = str(uuid.uuid4())
    mod = module.Module(
        id=mid,
        name="M",
        type=module.ModuleType.VISION,
        ip_address="1.2.3.4",
        port=1111,
        last_online=datetime.now(timezone.utc),
        status=module.StatusEnum.IDLE,
        robot_id="no-such-robot"
    )
    sess.add(mod)
    sess.commit()

    monkeypatch.setattr(sys, "argv", ["prog", mid])
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "ERROR: robot no-such-robot not found." in out

def test_status_loop_updates_and_sends(monkeypatch, capsys):
    # create one robot + module
    sess = module.Session()
    rid = str(uuid.uuid4())
    robot = module.Robot(id=rid, ip_address="127.0.0.1", port=9999)
    sess.add(robot)

    mid = str(uuid.uuid4())
    mod = module.Module(
        id=mid,
        name="ModA",
        type=module.ModuleType.IMU,
        ip_address="5.6.7.8",
        port=2222,
        last_online=datetime.now(timezone.utc),
        status=module.StatusEnum.IDLE,
        robot_id=rid
    )
    sess.add(mod)
    sess.commit()

    # argv
    monkeypatch.setattr(sys, "argv", ["prog", mid])

    # sequence: invalid → valid → KeyboardInterrupt
    inputs = iter(["BAD_STATUS", "FAILED", KeyboardInterrupt()])
    def fake_input(prompt=""):
        val = next(inputs)
        if isinstance(val, Exception):
            raise val
        return val
    monkeypatch.setattr(builtins, "input", fake_input)

    # capture the one FakeSocket instance
    created = []
    def fake_socket(*args, **kwargs):
        s = FakeSocket()
        created.append(s)
        return s
    monkeypatch.setattr(module.socket, "socket", fake_socket)

    # run (should not SystemExit)
    module.main()

    # check printed output
    out = capsys.readouterr().out
    assert "current status: IDLE" in out
    assert "Invalid status. Choose one of:" in out
    assert "STATUS: FAILED" not in out  # that's for server side
    assert "Updated → status=FAILED" in out
    assert "Sent →" in out
    assert "\nExiting." in out

    # verify DB was updated
    sess2 = module.Session()
    m2 = sess2.query(module.Module).get(mid)
    assert m2.status == module.StatusEnum.FAILED

    # verify socket send
    assert len(created) == 1
    sock = created[0]
    assert sock.connected_to == ("127.0.0.1", 9999)
    expected = {"module_id": mid, "status": "FAILED"}
    assert sock.sent_data == json.dumps(expected).encode("utf-8")
