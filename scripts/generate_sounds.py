"""
Generates the placeholder V1 feedback sounds under assets/sounds/.

These are synthesized tones, not real audio assets — deliberately so:
bundling actual Path of Exile game sounds would be a licensing problem,
and the directive itself says not to lock in exact final sound files
before that's explicitly settled. Re-run this script any time to
regenerate/tweak them; nothing at runtime depends on how they were made.
"""

import math
import struct
import wave
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "sounds"
SAMPLE_RATE = 44100


def _tone(frequency, duration_seconds, amplitude=0.4):
    sample_count = int(SAMPLE_RATE * duration_seconds)
    samples = []

    fade_samples = max(1, int(sample_count * 0.08))

    for i in range(sample_count):
        envelope = 1.0

        if i < fade_samples:
            envelope = i / fade_samples
        elif i > sample_count - fade_samples:
            envelope = (sample_count - i) / fade_samples

        value = amplitude * envelope * math.sin(
            2 * math.pi * frequency * (i / SAMPLE_RATE)
        )

        samples.append(value)

    return samples


def _concat(*tone_lists):
    combined = []
    for tones in tone_lists:
        combined.extend(tones)
    return combined


def _write_wav(filename, samples):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename

    with wave.open(str(path), "w") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)

        frames = b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, sample)) * 32767))
            for sample in samples
        )

        wav_file.writeframes(frames)

    print(f"wrote {path}")


def main():
    # Tier 1 (0–200c profit): a single short, modest beep.
    _write_wav("tink_small.wav", _tone(880, 0.12, amplitude=0.35))

    # Tier 2 (200–800c profit): two ascending notes.
    _write_wav(
        "tink_medium.wav",
        _concat(_tone(880, 0.10, amplitude=0.4), _tone(1174, 0.16, amplitude=0.45))
    )

    # Tier 3 (800c+ profit): three ascending notes, brighter and longer.
    _write_wav(
        "tink_large.wav",
        _concat(
            _tone(880, 0.09, amplitude=0.45),
            _tone(1174, 0.09, amplitude=0.5),
            _tone(1568, 0.22, amplitude=0.55),
        )
    )

    # Any loss: a low, somber descending tone.
    _write_wav(
        "warning.wav",
        _concat(_tone(220, 0.18, amplitude=0.4), _tone(146, 0.28, amplitude=0.4))
    )


if __name__ == "__main__":
    main()
