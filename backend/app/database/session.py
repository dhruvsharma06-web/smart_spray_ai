from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings

db_url = settings.database_url
connect_args = {}
if "sqlite" in db_url:
    db_url = db_url.replace("sqlite+aiosqlite://", "sqlite://")
    connect_args = {"check_same_thread": False}

engine = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
