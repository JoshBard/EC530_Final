# tests/test_cli.py

import builtins
import getpass
import pytest

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from .. import module_creator
from .. import robot_creator

@pytest.fixture(autouse=True)
def in_memory_dbs(monkeypatch):
    """
    Replace both modules' engine and Session with an in-memory SQLite database,
    and create all tables before each test.
    """
    # --- robot_creator DB patch ---
    r_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    r_Session = sessionmaker(bind=r_engine)
    monkeypatch.setattr(robot_creator, "engine", r_engine)
    monkeypatch.setattr(robot_creator, "Session", r_Session)
    robot_creator.Base.metadata.create_all(r_engine)

    # --- module_creator DB patch ---
    m_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    m_Session = sessionmaker(bind=m_engine)
    monkeypatch.setattr(module_creator, "engine", m_engine)
    monkeypatch.setattr(module_creator, "Session", m_Session)
    module_creator.Base.metadata.create_all(m_engine)

    yield

def test_robot_table_created():
    inspector = inspect(robot_creator.engine)
    tables = inspector.get_table_names()
    assert "robots" in tables

def test_module_table_created():
    inspector = inspect(module_creator.engine)
    tables = inspector.get_table_names()
    assert "robots" in tables
    assert "modules" in tables

def test_robot_main_creates_robot(monkeypatch, capsys):
    # simulate user inputs: name, owner, email, status, power, ssid, pwd, ip, port
    inputs = iter([
        "Robo1",                
        "Alice",                
        "alice@example.com",    
        "IDLE",                 
        "0.75",                 
        "TestSSID",             
        "TestNetPass",          
        "10.0.0.42",            
        "4242",                 
    ])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(inputs))
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "s3cretpw")

    # run the CLI
    robot_creator.main()

    # verify one robot in DB
    sess = robot_creator.Session()
    robots = sess.query(robot_creator.Robot).all()
    assert len(robots) == 1
    r = robots[0]
    assert r.name == "Robo1"
    assert r.owner == "Alice"
    assert r.owner_email == "alice@example.com"
    assert r.status == robot_creator.StatusEnum.IDLE
    assert abs(r.power_level - 0.75) < 1e-6
    assert r.network_ssid == "TestSSID"
    assert r.network_password == "TestNetPass"
    assert r.ip_address == "10.0.0.42"
    assert r.port == 4242
    assert r.password == "s3cretpw"

    out = capsys.readouterr().out
    assert "Created Robot 'Robo1'" in out

def test_choose_robot(monkeypatch, capsys):
    # insert one robot into module_creator's DB
    sess = module_creator.Session()
    sess.add(module_creator.Robot(id="robotX"))
    sess.commit()

    # simulate user selecting "robotX"
    monkeypatch.setattr(builtins, "input", lambda prompt="": "robotX")

    rid = module_creator.choose_robot(sess)
    out = capsys.readouterr().out

    assert "Available robot UUIDs:" in out
    assert "robotX" in out
    assert rid == "robotX"

def test_module_main_creates_module(monkeypatch, capsys):
    # prep a robot for modules to attach to
    sess = module_creator.Session()
    sess.add(module_creator.Robot(id="robotY"))
    sess.commit()

    # bypass choose_robot prompt
    monkeypatch.setattr(module_creator, "choose_robot", lambda sess_arg: "robotY")

    # inputs: name, type, ip, port, status
    inputs = iter([
        "modA",         # Module Name
        "VISION",       # Module Type
        "192.168.1.5",  # Module IP Address
        "5000",         # Module Port
        "RUNNING",      # Initial Status
    ])
    monkeypatch.setattr(builtins, "input", lambda prompt="": next(inputs))

    # run the CLI
    module_creator.main()

    # verify one module in DB
    sess2 = module_creator.Session()
    mods = sess2.query(module_creator.Module).all()
    assert len(mods) == 1

    mod = mods[0]
    assert mod.name == "modA"
    assert mod.type == module_creator.ModuleType.VISION
    assert mod.ip_address == "192.168.1.5"
    assert mod.port == 5000
    assert mod.status == module_creator.StatusEnum.RUNNING
    assert mod.robot_id == "robotY"

    out = capsys.readouterr().out
    assert "Created Module 'modA'" in out
