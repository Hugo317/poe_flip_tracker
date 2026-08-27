# PyInstaller spec for DivineFlipper. Build with:
#   pyinstaller divineflipper.spec
#
# Bundles assets/ (fonts, sounds — whatever exists at build time,
# since the .mp3 sound files are gitignored/personal and only the
# .wav fallbacks exist on a fresh checkout) and the Alembic migration
# files, since backend/migrations.py applies them itself at startup
# rather than relying on the alembic CLI being available.

import sys
from pathlib import Path

block_cipher = None

project_root = Path(SPECPATH)

datas = [
    (str(project_root / "assets"), "assets"),
    (str(project_root / "backend" / "data"), "backend/data"),
    (str(project_root / "alembic.ini"), "."),
    (str(project_root / "alembic" / "env.py"), "alembic"),
    (str(project_root / "alembic" / "script.py.mako"), "alembic"),
]

# assets/ above already covers assets/fonts and assets/sounds, which
# ui/main_window.py and ui/sound_player.py locate via a __file__-
# relative path — that keeps working once frozen only because this
# entry preserves the same "assets/" layout alongside the executable.

for migration_file in sorted(
    (project_root / "alembic" / "versions").glob("*.py")
):
    datas.append((str(migration_file), "alembic/versions"))

a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "alembic.op",
        "alembic.context",
        # alembic/env.py is bundled as a data file (Alembic loads and
        # execs it directly at runtime), so PyInstaller's static
        # import analysis never sees what it imports — everything it
        # needs has to be listed here explicitly instead.
        "logging.config",
        "sqlalchemy.pool",
        "sqlalchemy.engine",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DivineFlipper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DivineFlipper",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="DivineFlipper.app",
        icon=None,
        bundle_identifier="com.divineflipper.app",
    )
