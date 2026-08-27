from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "divineflipper.db"


def _enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def build_engine(db_path=DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(f"sqlite:///{db_path}")
    event.listen(engine, "connect", _enable_foreign_keys)

    return engine


def build_session_factory(engine):
    # expire_on_commit stays at SQLAlchemy's default (True): TradeService
    # holds one long-lived session for the app's lifetime, so anything
    # cached from before a commit (e.g. a Trade's `sales` relationship)
    # must be forced to reload afterward, or later-added rows can go
    # silently invisible to code that already touched that attribute
    # earlier in the session.
    return sessionmaker(bind=engine)
