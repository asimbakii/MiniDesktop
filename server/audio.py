"""Ses mikseri: platforma göre uygun uygulamayı seçer."""
import sys

if sys.platform == "win32":
    from audio_win import Audio  # noqa: F401  Windows Core Audio (pycaw)
else:
    from audio_linux import Audio  # noqa: F401  PulseAudio / PipeWire (pulsectl)
