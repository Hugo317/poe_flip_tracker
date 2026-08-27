import shutil
import sys
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.db.models import Base


def _default_data_dir():
    # OS-appropriate user-data location (directive 41: user data must
    # live separately from application binaries/assets) — critical
    # once packaged, since a frozen app's own directory is read-only
    # and doesn't travel with the user across upgrades.
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        import os
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".local" / "share"

    return base / "DivineFlipper"


def _legacy_repo_relative_db_path():
    # Where DB_PATH used to live (relative to this source file) —
    # only relevant for a one-time migration below, and only exists
    # at all in a dev checkout, never in a packaged build.
    return (
        Path(__file__).resolve().parent.parent.parent
        / "data" / "divineflipper.db"
    )


def _migrate_legacy_db_if_needed(db_path):
    legacy_path = _legacy_repo_relative_db_path()

    if db_path.exists() or not legacy_path.exists():
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy_path, db_path)

    legacy_backups = legacy_path.parent / "backups"
    if legacy_backups.exists():
        shutil.copytree(
            legacy_backups, db_path.parent / "backups",
            dirs_exist_ok=True
        )


DB_PATH = _default_data_dir() / "divineflipper.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
_migrate_legacy_db_if_needed(DB_PATH)


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
