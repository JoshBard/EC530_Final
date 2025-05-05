import sys
import socket
import json
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    DateTime,
    Enum as SAEnum,
    ForeignKey
)
from sqlalchemy.orm import sessionmaker, declarative_base

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
    last_online = Column(DateTime, nullable=False)
    status      = Column(SAEnum(StatusEnum), nullable=False)
    robot_id    = Column(String, ForeignKey("robots.id"), nullable=False)

# default database (can be monkeypatched in tests)
engine = create_engine("sqlite:///robots.db")
Session = sessionmaker(bind=engine)

def main():
    if len(sys.argv) != 2:
        print("Usage: module <module_id>")
        sys.exit(1)

    module_id = sys.argv[1]
    session = Session()

    module_obj = session.query(Module).filter_by(id=module_id).first()
    if not module_obj:
        print(f"ERROR: module {module_id} not found.")
        session.close()
        sys.exit(1)

    robot_obj = session.query(Robot).filter_by(id=module_obj.robot_id).first()
    if not robot_obj:
        print(f"ERROR: robot {module_obj.robot_id} not found.")
        session.close()
        sys.exit(1)

    print(f"Module {module_obj.id} ({module_obj.name}) current status: {module_obj.status.value}")
    print(f"→ sending updates to {robot_obj.ip_address}:{robot_obj.port}\n")

    while True:
        try:
            raw = input("Enter new status (RUNNING, IDLE, FAILED): ")
        except KeyboardInterrupt:
            print("\nExiting.")
            break

        if not isinstance(raw, str):
            print("\nExiting.")
            break

        status_str = raw.strip().upper()
        if status_str not in [s.value for s in StatusEnum]:
            print(f"Invalid status. Choose one of: {', '.join([s.value for s in StatusEnum])}")
            continue

        module_obj.status = StatusEnum(status_str)
        module_obj.last_online = datetime.now(timezone.utc)
        session.commit()
        print(f"Updated → status={module_obj.status.value}, last_online={module_obj.last_online.isoformat()}")

        payload = {"module_id": module_obj.id, "status": module_obj.status.value}
        with socket.socket() as sock:
            sock.connect((robot_obj.ip_address, robot_obj.port))
            sock.sendall(json.dumps(payload).encode("utf-8"))
            print(f"Sent → {payload}")

    session.close()
    return

if __name__ == "__main__":
    main()
