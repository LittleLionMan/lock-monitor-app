from sqlalchemy import create_engine, String, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
from datetime import datetime, timezone
from typing import Optional, Any
import os

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    card_uid: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    strike_1_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    strike_2_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    counter: Mapped[int] = mapped_column(default=0)
    last_violation_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

_engine: Optional[Any] = None
_Session: Optional[Any] = None
_database_initialized: bool = False

def create_database(db_path: str = 'data/app_database.db') -> Any:
    global _engine, _Session, _database_initialized

    if _database_initialized:
        return _engine

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    db_exists = os.path.exists(db_path)

    _engine = create_engine(f'sqlite:///{db_path}', echo=False, pool_pre_ping=True)
    _Session = sessionmaker(bind=_engine)

    if not db_exists:
        Base.metadata.create_all(_engine)
        print(f"Database created at: {db_path}")
    else:
        print(f"Database already exists at: {db_path}")

    _database_initialized = True

    return _engine

def get_session(db_path: str = 'data/app_database.db') -> Session:
    global _Session, _database_initialized

    if not _database_initialized:
        create_database(db_path)

    if _Session is None:
        raise RuntimeError("Database session factory not initialized")

    return _Session()

def get_engine() -> Optional[Any]:
    global _engine
    return _engine

def reset_database_state() -> None:
    global _engine, _Session, _database_initialized
    _engine = None
    _Session = None
    _database_initialized = False

if __name__ == "__main__":
    print("Creating database...")
    create_database()
    print("Database setup completed!")
