import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
import shutil
from datetime import datetime

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
    cursor.execute("PRAGMA busy_timeout=2000")
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



# =================================================================
# Backup Utilities (note: not used, just for demonstration)
# =================================================================

def prepare_for_backup():
    """Checkpoint WAL before backup to ensure consistency."""
    conn = engine.raw_connection()
    cursor = conn.cursor()
<<<<<<< HEAD

=======
>>>>>>> e6ecf58de01bb27f8dfd2d915429910e002d504c
    # RESTART mode: checkpoint everything and restart WAL
    cursor.execute("PRAGMA wal_checkpoint(RESTART)")
    cursor.close()
    conn.close()


def backup_database():
    """Create a timestamped backup of the database."""
<<<<<<< HEAD
=======
    import shutil
    from datetime import datetime
>>>>>>> e6ecf58de01bb27f8dfd2d915429910e002d504c

    # Checkpoint WAL first
    prepare_for_backup()

<<<<<<< HEAD
    # Get backup directory
    backup_dir = os.getenv("BACKUP_DIR")
=======
    # Get backup directory from env or default to backup/
    backup_dir = os.getenv("BACKUP_DIR", "backup")
>>>>>>> e6ecf58de01bb27f8dfd2d915429910e002d504c

    # Get DB path from DB_URL
    db_path = DB_URL.replace("sqlite:///", "")

    # Create backup directory
    os.makedirs(backup_dir, exist_ok=True)

    # Create timestamped backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f"backup_{timestamp}.db")

    shutil.copy2(db_path, backup_path)
    return backup_path
