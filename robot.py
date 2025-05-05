#!/usr/bin/env python3

import enum
import uuid
import threading
import socket
import json
import getpass
import sys
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, String, Integer, Float,
    DateTime, Enum as SAEnum, ForeignKey, event
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()

class StatusEnum(enum.Enum):
    RUNNING = "RUNNING"
    IDLE    = "IDLE"
    FAILED  = "FAILED"

class ModuleType(enum.Enum):
    VISION   = "VISION"
    MOTION   = "MOTION"
    IMU      = "IMU"
    ACTUATOR = "ACTUATOR"

class Robot(Base):
    __tablename__ = "robots"
    id               = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name             = Column(String, nullable=False)
    owner            = Column(String, nullable=False)
    owner_email      = Column(String, nullable=False)
    status           = Column(SAEnum(StatusEnum), default=StatusEnum.IDLE, nullable=False)
    last_online      = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc).replace(microsecond=0),
        nullable=False
    )
    power_level      = Column(Float, default=0.0)
    network_ssid     = Column(String, nullable=False)
    network_password = Column(String, nullable=False)
    ip_address       = Column(String, nullable=False)
    port             = Column(Integer, nullable=False)
    password         = Column(String, nullable=False)
    modules          = relationship("Module", back_populates="robot", cascade="all, delete-orphan")

@event.listens_for(Robot, "load")
def _attach_utc_tz_on_load(target: Robot, context):
    lo = target.last_online
    if lo is not None and lo.tzinfo is None:
        target.last_online = lo.replace(tzinfo=timezone.utc)

class Module(Base):
    __tablename__ = "modules"
    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name        = Column(String, nullable=False)
    type        = Column(SAEnum(ModuleType), nullable=False)
    ip_address  = Column(String, nullable=False)
    port        = Column(Integer, nullable=False)
    last_online = Column(DateTime)
    status      = Column(SAEnum(StatusEnum), default=StatusEnum.IDLE, nullable=False)
    robot_id    = Column(String, ForeignKey("robots.id"), nullable=False)
    robot       = relationship("Robot", back_populates="modules")

DATABASE_URL = "sqlite:///./robots.db"
engine       = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session      = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

def select_or_create_robot(session):
    robots = session.query(Robot).all()
    if not robots:
        print("No robots found; creating one:")
        data = {
            "name":             input("  Name: "),
            "owner":            input("  Owner: "),
            "owner_email":      input("  Owner email: "),
            "network_ssid":     input("  Network SSID: "),
            "network_password": input("  Network password: "),
            "ip_address":       input("  Robot IP address: "),
            "port":             int(input("  Robot port: ")),
            "password":         getpass.getpass("  Set robot password: ")
        }
        robot = Robot(**data)
        session.add(robot)
        session.commit()
        print(f"Created robot '{robot.name}' ({robot.id})\n")
        return robot

    if len(robots) == 1:
        robot = robots[0]
    else:
        print("Select a robot:")
        for r in robots:
            print(f"  {r.id}: {r.name}")
        sel = input("Enter robot ID: ")
        robot = session.query(Robot).get(sel)
        if not robot:
            print("Invalid ID"); sys.exit(1)

    pw = getpass.getpass("Enter robot password: ")
    if pw != robot.password:
        print("Incorrect password"); sys.exit(1)
    return robot

def handle_client(conn, robot_id):
    sess = Session()
    raw = conn.recv(1024)
    try:
        msg             = json.loads(raw.decode())
        module_id       = msg["module_id"]
        incoming_status = StatusEnum[msg["status"]]
    except Exception:
        sess.close()
        return

    # Gather all modules for this robot
    modules = sess.query(Module).filter_by(robot_id=robot_id).all()

    # Determine new robot status
    if any(m.status == StatusEnum.FAILED for m in modules):
        robot_status = StatusEnum.FAILED
    elif any(m.status == StatusEnum.RUNNING for m in modules):
        robot_status = StatusEnum.RUNNING
    else:
        robot_status = StatusEnum.IDLE

    # Update robot row
    robot = sess.query(Robot).get(robot_id)
    robot.status      = robot_status
    # <<<< use full-precision UTC timestamp here >>>>
    robot.last_online = datetime.now(timezone.utc)
    sess.add(robot)
    sess.commit()

    # On an incoming FAILED, print alert for that module
    if incoming_status is StatusEnum.FAILED:
        mod = sess.query(Module).get(module_id)
        print(
            "\033[91mSTATUS: FAILED\033[0m  "
            f"Module '{mod.name}' ({mod.id}) @ {mod.ip_address}:{mod.port}"
        )

    sess.close()

def socket_server(robot):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((robot.ip_address, robot.port))
    srv.listen()
    print(f"Listening on {robot.ip_address}:{robot.port}")
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle_client, args=(conn, robot.id), daemon=True).start()

if __name__ == "__main__":
    sess = Session()
    robo = select_or_create_robot(sess)
    print(f"Running robot '{robo.name}' [{robo.id}]  (status={robo.status.name})")
    socket_server(robo)
