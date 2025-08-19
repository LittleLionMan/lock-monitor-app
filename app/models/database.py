from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
import os

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    card_uid = Column(String(50), unique=True, nullable=False, index=True)
    strike_1_date = Column(DateTime, nullable=True)  # Datum von Strike 1
    strike_2_date = Column(DateTime, nullable=True)  # Datum von Strike 2
    counter = Column(Integer, default=0)             # Counter für Strike 3+
    last_violation_date = Column(DateTime, nullable=True)  # Letzter Verstoß
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

# Database setup
def create_database(db_path='data/app_database.db'):
    """Create database and tables if they don't exist"""

    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    db_exists = os.path.exists(db_path)

    engine = create_engine(f'sqlite:///{db_path}', echo=False)

    if not db_exists:
        Base.metadata.create_all(engine)
        print(f"Database created at: {db_path}")
    else:
        print(f"Database already exists at: {db_path}")

    return engine

def get_session(db_path='data/app_database.db'):
    """Get database session"""
    engine = create_database(db_path)
    Session = sessionmaker(bind=engine)
    return Session()

if __name__ == "__main__":
    print("Creating database...")
    create_database()
    print("Database setup completed!")
