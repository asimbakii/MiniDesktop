"""Windows panosu (Win32 API, ctypes)."""
import ctypes
import ctypes.wintypes as wt
import time

from i18n import t

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32.OpenClipboard.argtypes = [wt.HWND]
user32.OpenClipboard.restype = wt.BOOL
user32.GetClipboardData.argtypes = [wt.UINT]
user32.GetClipboardData.restype = wt.HANDLE
user32.SetClipboardData.argtypes = [wt.UINT, wt.HANDLE]
user32.SetClipboardData.restype = wt.HANDLE
user32.IsClipboardFormatAvailable.argtypes = [wt.UINT]
user32.RegisterClipboardFormatW.argtypes = [wt.LPCWSTR]
user32.RegisterClipboardFormatW.restype = wt.UINT
user32.GetClipboardSequenceNumber.restype = wt.DWORD
kernel32.GlobalAlloc.argtypes = [wt.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wt.HGLOBAL
kernel32.GlobalLock.argtypes = [wt.HGLOBAL]
kernel32.GlobalLock.restype = wt.LPVOID
kernel32.GlobalUnlock.argtypes = [wt.HGLOBAL]
kernel32.GlobalSize.argtypes = [wt.HGLOBAL]
kernel32.GlobalSize.restype = ctypes.c_size_t
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
# Şifre yöneticileri bu formatları ekler: bu içerikleri geçmişe alma
_PRIVATE = [user32.RegisterClipboardFormatW(n) for n in ("ExcludeClipboardContentFromMonitorProcessing", "Clipboard Viewer Ignore")]
_CAN_INCLUDE = user32.RegisterClipboardFormatW("CanIncludeInClipboardHistory")


def _open_clipboard():
    for _ in range(20):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def clipboard_get() -> str | None:
    if any(user32.IsClipboardFormatAvailable(f) for f in _PRIVATE):
        return None
    if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT) or not _open_clipboard():
        return None
    try:
        if user32.IsClipboardFormatAvailable(_CAN_INCLUDE):
            h = user32.GetClipboardData(_CAN_INCLUDE)
            p = kernel32.GlobalLock(h) if h else None
            if p:
                allowed = ctypes.c_uint32.from_address(p).value
                kernel32.GlobalUnlock(h)
                if allowed == 0:
                    return None
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return None
        p = kernel32.GlobalLock(h)
        if not p:
            return None
        try:
            return ctypes.wstring_at(p)
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def clipboard_set(text: str):
    data = (text + "\0").encode("utf-16-le")
    if not _open_clipboard():
        raise RuntimeError(t("Pano şu an kullanımda, tekrar dene."))
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, data, len(data))
        kernel32.GlobalUnlock(h)
        if not user32.SetClipboardData(CF_UNICODETEXT, h):
            raise RuntimeError(t("Panoya yazılamadı."))
    finally:
        user32.CloseClipboard()


def clipboard_seq():
    """Pano her değiştiğinde artan sayaç."""
    return user32.GetClipboardSequenceNumber()
