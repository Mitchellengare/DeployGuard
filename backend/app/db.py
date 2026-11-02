from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Deployment(Base):
    __tablename__ = "deployments"
    id: Mapped[int] = mapped_column(primary_key=True)
    service: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[str] = mapped_column(String(100))
    commit_sha: Mapped[str] = mapped_column(String(64), default="")
    author: Mapped[str] = mapped_column(String(100), default="")
    changed_files: Mapped[list] = mapped_column(JSON, default=list)
    deployed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class LogEntry(Base):
    __tablename__ = "logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    service: Mapped[str] = mapped_column(String(100), index=True)
    level: Mapped[str] = mapped_column(String(10), index=True)
    message: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(primary_key=True)
    service: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    summary: Mapped[str] = mapped_column(Text, default="")
    top_patterns: Mapped[list] = mapped_column(JSON, default=list)
    suspects: Mapped[list["Suspect"]] = relationship(
        back_populates="incident", cascade="all, delete-orphan", order_by="Suspect.score.desc()"
    )


class Suspect(Base):
    __tablename__ = "suspects"
    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"))
    deployment_id: Mapped[int] = mapped_column(ForeignKey("deployments.id"))
    score: Mapped[float] = mapped_column()
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    incident: Mapped[Incident] = relationship(back_populates="suspects")
    deployment: Mapped[Deployment] = relationship()


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
