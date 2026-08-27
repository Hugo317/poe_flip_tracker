from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QSoundEffect

from backend.sound_rules import classify_sale_feedback

SOUNDS_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"

# Swap these files for real ones any time — same filenames, no code
# changes needed. See scripts/generate_sounds.py for how the current
# placeholders were made.
SOUND_FILES = {
    "tink_small": "tink_small.wav",
    "tink_medium": "tink_medium.wav",
    "tink_large": "tink_large.wav",
    "warning": "warning.wav",
}


class SoundPlayer:
    """Plays the loot-filter-style feedback sound for a sale, gated by
    the General settings toggles (directive Q49) — master volume,
    TINK enable, warnings enable. No-op for categories the settings
    have disabled, and silent (by design) for zero-profit sales."""

    def __init__(self, trade_service):
        self.trade_service = trade_service

        self._effects = {}

        for category, filename in SOUND_FILES.items():
            effect = QSoundEffect()
            effect.setSource(
                QUrl.fromLocalFile(str(SOUNDS_DIR / filename))
            )
            self._effects[category] = effect

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

        effect = self._effects[category]
        effect.setVolume(self.trade_service.sound_master_volume / 100)
        effect.play()
