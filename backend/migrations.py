import sys
from pathlib import Path

from alembic import command
from alembic.config import Config


def _base_dir():
    # Inside a PyInstaller bundle, alembic.ini and alembic/ are
    # bundled as data files and extracted to sys._MEIPASS at
    # runtime — everywhere else (dev, tests), it's just the repo
    # root two levels up from this file.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)

    return Path(__file__).resolve().parent.parent


def run_migrations():
    """Brings the database up to the latest schema. Packaged builds
    have no Python/Alembic CLI available to the end user, so this
    must happen automatically at every launch rather than relying on
    someone running `alembic upgrade head` by hand."""

    base_dir = _base_dir()

    config = Config(str(base_dir / "alembic.ini"))
    config.set_main_option("script_location", str(base_dir / "alembic"))

    command.upgrade(config, "head")
