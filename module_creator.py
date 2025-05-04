import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    create_engine, Column, String, Integer,
    DateTime, Enum as SAEnum, ForeignKey
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

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
    id = Column(String, primary_key=True)

class Module(Base):
    __tablename__ = "modules"
    id          = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name        = Column(String, nullable=False)
    type        = Column(SAEnum(ModuleType), nullable=False)
    ip_address  = Column(String, nullable=False)
    port        = Column(Integer, nullable=False)
    last_online = Column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc).replace(microsecond=0),nullable=False)
    status      = Column(SAEnum(StatusEnum), default=StatusEnum.IDLE, nullable=False)
    robot_id    = Column(String, ForeignKey("robots.id"), nullable=False)

# DB init
DATABASE_URL = "sqlite:///./robots.db"
engine       = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session      = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

def choose_robot(sess):
    robots = sess.query(Robot).all()
    print("Available robot UUIDs:")
    for r in robots:
        print(f"  {r.id}")
    rid = input("Enter target robot UUID: ").strip()
    return rid

def main():
    sess = Session()
    rid  = choose_robot(sess)

    name = input("Module Name: ").strip()

    # ModuleType
    while True:
        t = input("Module Type (VISION/MOTION/IMU/ACTUATOR): ").strip().upper()
        if t in ModuleType.__members__:
            mtype = ModuleType[t]
            break
        print("↳ invalid — choose one of VISION, MOTION, IMU, ACTUATOR")

    ip   = input("Module IP Address: ").strip()
    port = int(input("Module Port: "))

    # StatusEnum
    while True:
        s = input("Initial Status (RUNNING/IDLE/FAILED): ").strip().upper()
        if s in StatusEnum.__members__:
            stat = StatusEnum[s]
            break
        print("↳ invalid — choose RUNNING, IDLE, FAILED")

    mod = Module(
        name=name,
        type=mtype,
        ip_address=ip,
        port=port,
        status=stat,
        robot_id=rid
    )
    sess.add(mod)
    sess.commit()
    print(f"Created Module '{mod.name}' ({mod.id}) – status={mod.status.name}")
    sess.close()

if __name__ == "__main__":
    main()
