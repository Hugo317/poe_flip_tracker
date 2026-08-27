from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from backend.sound_rules import classify_sale_feedback

SOUNDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"

# Base names only — resolved to an actual file below. A local *.mp3
# (personal, gitignored — see .gitignore) is preferred when present;
# the committed *.wav placeholder is the always-available fallback, so
# a fresh clone with no personal sounds still works out of the box.
SOUND_BASE_NAMES = {
    "tink_small": "tink_small",
    "tink_medium": "tink_medium",
    "tink_large": "tink_large",
    "warning": "warning",
}

# QMediaPlayer (via Qt's FFmpeg backend) handles compressed formats
# like MP3 directly, unlike QSoundEffect, which is PCM/WAV-only and
# errors out on anything compressed — hence QMediaPlayer here even
# though the committed fallback files are plain WAV.
PREFERRED_EXTENSIONS = [".mp3", ".wav"]


def _resolve_sound_path(base_name):
    for extension in PREFERRED_EXTENSIONS:
        path = SOUNDS_DIR / f"{base_name}{extension}"
        if path.exists():
            return path

    return None


class SoundPlayer:
    """Plays the loot-filter-style feedback sound for a sale, gated by
    the General settings toggles (directive Q49) — master volume,
    TINK enable, warnings enable. No-op for categories the settings
    have disabled, and silent (by design) for zero-profit sales."""

    def __init__(self, trade_service):
        self.trade_service = trade_service

        self._players = {}
        self._audio_outputs = {}

        for category, base_name in SOUND_BASE_NAMES.items():
            path = _resolve_sound_path(base_name)

            if path is None:
                continue

            audio_output = QAudioOutput()

            player = QMediaPlayer()
            player.setAudioOutput(audio_output)
            player.setSource(QUrl.fromLocalFile(str(path)))

            self._players[category] = player
            self._audio_outputs[category] = audio_output

    def play_for_profit(self, profit):
        category = classify_sale_feedback(
            profit,
            tier_small_max=self.trade_service.sound_tier_small_max,
            tier_medium_max=self.trade_service.sound_tier_medium_max
        )

        if category == "neutral":
            return

        if category == "warning":
            if not self.trade_service.sound_warnings_enabled:
                return
        elif not self.trade_service.sound_tink_enabled:
            return

        if category not in self._players:
            return

        self._audio_outputs[category].setVolume(
            self.trade_service.sound_master_volume / 100
        )

        player = self._players[category]
        player.setPosition(0)
        player.play()
