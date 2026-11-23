"""Pano erişimi: platforma göre uygun uygulamayı seçer."""
import sys

if sys.platform == "win32":
    from clipboard_win import clipboard_get, clipboard_seq, clipboard_set  # noqa: F401
else:
    from clipboard_linux import clipboard_get, clipboard_seq, clipboard_set  # noqa: F401
