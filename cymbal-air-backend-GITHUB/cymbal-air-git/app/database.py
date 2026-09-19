import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# DATABASE_URL examples:
#   Local dev (default):        sqlite:///./cymbal_air.db
#   Cloud SQL Postgres (Cloud Run + Unix socket via Cloud SQL connector):
#       postgresql+psycopg2://USER:PASSWORD@/DBNAME?host=/cloudsql/PROJECT:REGION:INSTANCE
#   Any external Postgres:      postgresql+psycopg2://USER:PASSWORD@HOST:5432/DBNAME
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./cymbal_air.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
