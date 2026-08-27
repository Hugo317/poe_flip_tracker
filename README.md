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
Alembic migrations. The app applies migrations itself automatically at
every launch (`backend/migrations.py`, called at the top of `main()`)
— no manual `alembic upgrade head` needed, including for a first-ever
run or after pulling a new `alembic/versions/*.py` migration.

Running `alembic` commands by hand (e.g. `alembic revision
--autogenerate`) is still how you *create* a new migration during
development — just not how it gets applied anymore.

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

## Sounds

`assets/sounds/` holds the loot-filter-style feedback sounds played on
each SELL confirmation (partial or full — one sound per sale, based on
that sale's own profit): `tink_small`, `tink_medium`, `tink_large`,
`warning`.

The two tier boundaries (default 200c / 800c) are adjustable in
Settings > General, not hardcoded — a sale's profit below the first
boundary plays the small TINK, below the second a bigger one, at/above
it the biggest; any loss plays the warning sound; exactly 0 profit is
silent.

**Two layers of sound files, by design:**

- `*.wav` — committed, synthesized placeholder tones (see
  `scripts/generate_sounds.py`), always present after a fresh clone.
- `*.mp3` — an optional personal override, gitignored. `SoundPlayer`
  (`ui/sound_player.py`) prefers the `.mp3` when present, falling back
  to the committed `.wav` otherwise.

This split exists because Hugo's current `.mp3` files came from a
SoundCloud account with unconfirmed reuse rights — real audio someone
downloaded, not a licensed sound-effects pack, so it stays off the
public repo entirely rather than getting committed and distributed.
Playback uses `QMediaPlayer`/`QAudioOutput` (Qt's FFmpeg-backed
multimedia stack) specifically so it can handle compressed formats
like MP3 — `QSoundEffect` only decodes PCM/WAV and errors on anything
compressed. Playback also respects the master volume / enable-TINK /
enable-warnings toggles in the same Settings section.

## Run

```bash
source ~/.venvs/poe_flip_tracker/bin/activate
cd /path/to/poe_flip_tracker
python3 -m ui.main_window
```

Run it as a module (`-m ui.main_window`), not as a script
(`python3 ui/main_window.py`) — the latter doesn't put the project root
on `sys.path`, so `backend` won't be importable.
