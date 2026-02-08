import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

# Default to SQLite database
DB_URL = os.getenv("DB_URL")

# handle concurrency
engine = create_engine(
    DB_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 5  # Reduced to 5s (better for banking apps)
    },
    pool_size=5, 
    max_overflow=10,
    # check if connection is alive
    pool_pre_ping=True
)


# Enable WAL mode for SQLite -> better concurrency
# configures every time connection with db is initialized
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    # Enable WAL (Write-Ahead Logging) mode
    cursor.execute("PRAGMA journal_mode=WAL")
    # ensure all data is written in case of errors
    cursor.execute("PRAGMA synchronous=FULL")
    # if the lock is busy, wait up to 2 seconds before throwing an error
    cursor.execute("PRAGMA busy_timeout=2s000")
    # Cache size
    cursor.execute("PRAGMA cache_size=-64000")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
