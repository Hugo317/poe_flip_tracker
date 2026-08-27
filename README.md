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

## Run

```bash
source ~/.venvs/poe_flip_tracker/bin/activate
cd /path/to/poe_flip_tracker
python3 -m ui.main_window
```

Run it as a module (`-m ui.main_window`), not as a script
(`python3 ui/main_window.py`) — the latter doesn't put the project root
on `sys.path`, so `backend` won't be importable.
