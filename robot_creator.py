import enum
import uuid
from datetime import datetime, timezone
import getpass

from sqlalchemy import (
    create_engine, Column, String, Integer, Float,
    DateTime, Enum as SAEnum
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class StatusEnum(enum.Enum):
    RUNNING = "RUNNING"
    IDLE    = "IDLE"
    FAILED  = "FAILED"

class Robot(Base):
    __tablename__ = "robots"
    id               = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name             = Column(String, nullable=False)
    owner            = Column(String, nullable=False)
    owner_email      = Column(String, nullable=False)
    status           = Column(SAEnum(StatusEnum), default=StatusEnum.IDLE, nullable=False)
    last_online      = Column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc).replace(microsecond=0),nullable=False)
    power_level      = Column(Float, default=0.0)
    network_ssid     = Column(String, nullable=False)
    network_password = Column(String, nullable=False)
    ip_address       = Column(String, nullable=False)
    port             = Column(Integer, nullable=False)
    password         = Column(String, nullable=False)

# DB init
DATABASE_URL = "sqlite:///./robots.db"
engine       = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
Session      = sessionmaker(bind=engine)
Base.metadata.create_all(engine)

def main():
    sess = Session()
    name  = input("Name: ").strip()
    owner = input("Owner: ").strip()
    email = input("Owner Email: ").strip()

    # StatusEnum
    while True:
        s = input("Initial Status (RUNNING/IDLE/FAILED): ").strip().upper()
        if s in StatusEnum.__members__:
            stat = StatusEnum[s]
            break
        print("↳ invalid — choose RUNNING, IDLE, or FAILED")

    power = float(input("Power Level (0.0–1.0): "))

    ssid = input("Network SSID: ").strip()
    pwd  = input("Network Password: ").strip()
    ip   = input("Robot IP Address: ").strip()
    port = int(input("Robot Port: "))

    passwd = getpass.getpass("Set Robot Password: ")

    robot = Robot(
        name=name,
        owner=owner,
        owner_email=email,
        status=stat,
        power_level=power,
        network_ssid=ssid,
        network_password=pwd,
        ip_address=ip,
        port=port,
        password=passwd
    )
    sess.add(robot)
    sess.commit()
    print(f"Created Robot '{robot.name}' ({robot.id}) – status={robot.status.name}")
    sess.close()

if __name__ == "__main__":
    main()
