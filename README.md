# poe_flip_tracker

DivineFlipper — a Path of Exile currency-flipping/trading tracker. See
`V1_APP_DIRECTIVES.md` for the full product spec.

## Setup

**The virtual environment must live outside `~/Documents` (or any other
TCC-protected macOS folder).** Qt's own plugin-directory scan silently
returns zero files when the plugins live under a protected folder, even
though Python's own `os.listdir` sees them fine and no permission dialog
or error is ever shown — it just fails with:

```
qt.qpa.plugin: Could not find the Qt platform plugin "cocoa" in ""
```

The project code can stay wherever you cloned it (including under
`~/Documents`); only the venv needs to be elsewhere.

```bash
python3 -m venv ~/.venvs/poe_flip_tracker
source ~/.venvs/poe_flip_tracker/bin/activate
pip install -r requirements.txt
```

## Database

Data is stored locally in SQLite at `data/divineflipper.db` (gitignored
— it's per-machine user data, not something to commit), managed with
Alembic migrations. Before the first run, create the database:

```bash
source ~/.venvs/poe_flip_tracker/bin/activate
alembic upgrade head
```

Run this again after pulling any change that adds a new
`alembic/versions/*.py` migration file.

## Asset catalog & image cache

The tradeable-item picker is populated live from
[poe.ninja](https://poe.ninja)'s public economy API (currently the
"Standard" league — see `backend/assets_service.py` and
`backend/providers/poe_ninja.py`). On launch, the app refreshes the
catalog and downloads any missing item icons to an OS-appropriate cache
directory, separate from the database:

- macOS: `~/Library/Caches/DivineFlipper/images/`
- Linux: `~/.cache/DivineFlipper/images/`
- Windows: `%LOCALAPPDATA%\DivineFlipper\images\`

This is a plain download cache (not committed, not backed up) — safe to
delete; it just gets rebuilt on the next launch with internet access.
If poe.ninja is unreachable, the app falls back to whatever was cached
from the last successful refresh and continues working offline.

## Run

```bash
source ~/.venvs/poe_flip_tracker/bin/activate
cd /path/to/poe_flip_tracker
python3 -m ui.main_window
```

Run it as a module (`-m ui.main_window`), not as a script
(`python3 ui/main_window.py`) — the latter doesn't put the project root
on `sys.path`, so `backend` won't be importable.
