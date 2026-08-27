import sqlite3
import time

from backend.backup import BackupManager


def _write_marker(db_path, value):
    connection = sqlite3.connect(db_path)
    connection.execute("CREATE TABLE IF NOT EXISTS marker (value TEXT)")
    connection.execute("DELETE FROM marker")
    connection.execute("INSERT INTO marker VALUES (?)", (value,))
    connection.commit()
    connection.close()


def _read_marker(db_path):
    connection = sqlite3.connect(db_path)
    value = connection.execute("SELECT value FROM marker").fetchone()[0]
    connection.close()
    return value


def test_create_backup_writes_db_copy_and_sql_dump(tmp_path):
    db_path = tmp_path / "test.db"
    _write_marker(db_path, "hello")

    manager = BackupManager(db_path=db_path, backup_dir=tmp_path / "backups")
    backup_path = manager.create_backup()

    assert backup_path.exists()
    assert backup_path.suffix == ".db"
    assert backup_path.with_suffix(".sql").exists()
    assert _read_marker(backup_path) == "hello"


def test_run_daily_backup_if_needed_is_idempotent_same_day(tmp_path):
    db_path = tmp_path / "test.db"
    _write_marker(db_path, "v1")

    manager = BackupManager(db_path=db_path, backup_dir=tmp_path / "backups")

    first = manager.run_daily_backup_if_needed()
    second = manager.run_daily_backup_if_needed()

    assert first is not None
    assert second is None  # already have one for today
    assert len(manager.list_backups()) == 1


def test_restore_backup_overwrites_live_db_and_keeps_safety_copy(tmp_path):
    db_path = tmp_path / "test.db"
    backup_dir = tmp_path / "backups"
    manager = BackupManager(db_path=db_path, backup_dir=backup_dir)

    _write_marker(db_path, "original")
    manager.create_backup()

    time.sleep(1.1)  # filenames are second-resolution timestamps
    _write_marker(db_path, "corrupted")
    manager.create_backup()

    backups = manager.list_backups()
    oldest_path, _ = backups[-1]

    manager.restore_backup(oldest_path)

    assert _read_marker(db_path) == "original"
    safety_copies = list(tmp_path.glob("test_before_restore_*.db"))
    assert len(safety_copies) == 1


def test_prune_old_backups_removes_stale_files(tmp_path):
    db_path = tmp_path / "test.db"
    _write_marker(db_path, "x")

    backup_dir = tmp_path / "backups"
    manager = BackupManager(db_path=db_path, backup_dir=backup_dir)
    manager.create_backup()

    assert len(manager.list_backups()) == 1

    manager.prune_old_backups(retention_days=0)

    assert len(manager.list_backups()) == 0
