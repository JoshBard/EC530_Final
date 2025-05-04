#!/usr/bin/env python3

import sys
import uuid
import socket
import json
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Enum as SAEnum,
    ForeignKey
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

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
    id         = Column(String, primary_key=True)
    ip_address = Column(String, nullable=False)
    port       = Column(Integer, nullable=False)

class Module(Base):
    __tablename__ = "modules"
    id          = Column(String, primary_key=True)
    name        = Column(String, nullable=False)
    type        = Column(SAEnum(ModuleType), nullable=False)
    ip_address  = Column(String, nullable=False)
    port        = Column(Integer, nullable=False)
    last_online = Column(DateTime(timezone=True))
    status      = Column(SAEnum(StatusEnum), default=StatusEnum.IDLE, nullable=False)
    robot_id    = Column(String, ForeignKey("robots.id"), nullable=False)
    robot       = relationship("Robot")

# ——— DB setup ———————————————————————————————
DATABASE_URL = "sqlite:///./robots.db"
engine       = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session      = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

# ——— CLI + prompt loop —————————————————————————

def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <module_uuid>")
        sys.exit(1)

    module_uuid = str(uuid.UUID(sys.argv[1]))
    session     = Session()

    module = session.query(Module).filter_by(id=module_uuid).first()
    if not module:
        print(f"ERROR: module {module_uuid} not found.")
        session.close()
        sys.exit(1)

    robot = session.query(Robot).filter_by(id=module.robot_id).first()
    if not robot:
        print(f"ERROR: robot {module.robot_id} not found.")
        session.close()
        sys.exit(1)

    print(f"Module {module.id} ({module.name}) current status: {module.status.value}")
    print(f"→ sending updates to {robot.ip_address}:{robot.port}\n")

    try:
        while True:
            status_str = input("Enter new status (RUNNING, IDLE, FAILED): ").strip().upper()
            if status_str not in StatusEnum.__members__:
                print("Invalid status. Choose one of:", ", ".join(StatusEnum.__members__))
                continue

            new_status = StatusEnum[status_str]
            module.status      = new_status
            module.last_online = datetime.now(timezone.utc).replace(microsecond=0)
            session.commit()

            # build and send JSON over TCP
            payload = {"module_id": module.id, "status": module.status.name}
            data    = json.dumps(payload).encode("utf-8")
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.connect((robot.ip_address, robot.port))
                    sock.sendall(data)
            except Exception as exc:
                print(f"Error sending to robot: {exc}")

            print(
                f"Updated → status={module.status.value}, "
                f"last_online={module.last_online.isoformat()}\n"
                f"Sent → {payload}"
            )

    except KeyboardInterrupt:
        print("\nExiting.")
    finally:
        session.close()

if __name__ == "__main__":
    main()
