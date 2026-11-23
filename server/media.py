"""Medya kontrolü: platforma göre uygun uygulamayı seçer."""
import sys

if sys.platform == "win32":
    from media_win import Media, app_label  # noqa: F401  Windows medya oturumları (WinRT)
else:
    from media_linux import Media, app_label  # noqa: F401  Linux MPRIS (D-Bus)
