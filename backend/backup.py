import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from backend.db.session import DB_PATH

RETENTION_DAYS = 15
BACKUP_DIR = DB_PATH.parent / "backups"


class BackupManager:
    """Directive Q4/Q5: one automatic backup per day (both a raw
    SQLite copy and a SQL dump), retained 15 days, plus a manual
    on-demand backup from Settings."""

    def __init__(self, db_path=DB_PATH, backup_dir=BACKUP_DIR):
        self.db_path = db_path
        self.backup_dir = backup_dir

    def run_daily_backup_if_needed(self):
        if not self.db_path.exists():
            return None

        today = datetime.now().strftime("%Y-%m-%d")

        if self._backup_exists_for(today):
            return None

        return self.create_backup()

    def create_backup(self):
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        db_backup_path = self.backup_dir / f"divineflipper_{timestamp}.db"
        sql_backup_path = self.backup_dir / f"divineflipper_{timestamp}.sql"

        shutil.copy2(self.db_path, db_backup_path)

        connection = sqlite3.connect(self.db_path)
        try:
            with sql_backup_path.open("w") as sql_file:
                for line in connection.iterdump():
                    sql_file.write(f"{line}\n")
        finally:
            connection.close()

        self.prune_old_backups()

        return db_backup_path

    def prune_old_backups(self, retention_days=RETENTION_DAYS):
        if not self.backup_dir.exists():
            return

        cutoff = datetime.now() - timedelta(days=retention_days)

        for path in self.backup_dir.glob("divineflipper_*.*"):
            created_at = self._parse_timestamp(path)

            if created_at is not None and created_at < cutoff:
                path.unlink()

    def last_backup_at(self):
        if not self.backup_dir.exists():
            return None

        db_backups = sorted(self.backup_dir.glob("divineflipper_*.db"))

        if not db_backups:
            return None

        return self._parse_timestamp(db_backups[-1])

    def list_backups(self):
        """(path, timestamp) pairs, newest first."""

        if not self.backup_dir.exists():
            return []

        backups = []

        for path in self.backup_dir.glob("divineflipper_*.db"):
            timestamp = self._parse_timestamp(path)

            if timestamp is not None:
                backups.append((path, timestamp))

        backups.sort(key=lambda pair: pair[1], reverse=True)

        return backups

    def restore_backup(self, backup_path):
        """Overwrites the live database with a backup. The app must
        be restarted afterward — restoring underneath a live SQLite
        connection is not safe. A safety copy of whatever was live
        just before the overwrite is kept, in case the wrong backup
        was chosen."""

        if self.db_path.exists():
            safety_timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            safety_path = self.db_path.with_name(
                f"{self.db_path.stem}_before_restore_"
                f"{safety_timestamp}{self.db_path.suffix}"
            )
            shutil.copy2(self.db_path, safety_path)

        shutil.copy2(backup_path, self.db_path)

    def _backup_exists_for(self, date_str):
        if not self.backup_dir.exists():
            return False

        return any(
            path.name.startswith(f"divineflipper_{date_str}")
            for path in self.backup_dir.glob("divineflipper_*.db")
        )

    def _parse_timestamp(self, path):
        # Filenames are always divineflipper_YYYY-MM-DD_HHMMSS.ext —
        # parsed from the name itself rather than file mtime, since
        # shutil.copy2 preserves the *source* database's mtime on the
        # .db copy, which reflects the last trade, not backup time.
        stem = path.stem.removeprefix("divineflipper_")

        try:
            return datetime.strptime(stem, "%Y-%m-%d_%H%M%S")
        except ValueError:
            return None
