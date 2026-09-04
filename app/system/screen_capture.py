"""Снимок экрана в настоящих пикселях, мимо Qt.

Приложение объявлено system-DPI-осведомлённым: так Qt не пересчитывает
раскладку при переносе окна между мониторами с разным масштабом. Плата за это
в том, что Windows отдаёт такому процессу виртуализированные координаты и
размеры — монитор 1920x1080 выглядит как 2880x1620.

Здесь мы на время снимка переключаем DPI-контекст потока в per-monitor и
работаем напрямую с GDI, поэтому получаем настоящие пиксели.
"""

import ctypes
import sys
from ctypes import wintypes

from PIL import Image

IS_WINDOWS = sys.platform == "win32"

SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
DIB_RGB_COLORS = 0

# DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)

ENUM_CURRENT_SETTINGS = -1


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmPositionX", ctypes.c_long),
        ("dmPositionY", ctypes.c_long),
        ("dmDisplayOrientation", wintypes.DWORD),
        ("dmDisplayFixedOutput", wintypes.DWORD),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]


if IS_WINDOWS:
    _user32 = ctypes.windll.user32
    _gdi32 = ctypes.windll.gdi32
    _user32.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p
    _user32.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]


class _RealPixels:
    """На время блока поток видит настоящие координаты и размеры экранов."""

    def __enter__(self):
        self._previous = None
        if IS_WINDOWS:
            self._previous = _user32.SetThreadDpiAwarenessContext(PER_MONITOR_AWARE_V2)
        return self

    def __exit__(self, *exc):
        if IS_WINDOWS and self._previous:
            _user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(self._previous))
        return False


def display_mode(device_name):
    """Настоящее разрешение и положение монитора: (x, y, width, height)."""
    if not IS_WINDOWS:
        return None
    mode = DEVMODE()
    mode.dmSize = ctypes.sizeof(DEVMODE)
    with _RealPixels():
        ok = _user32.EnumDisplaySettingsW(
            device_name, ENUM_CURRENT_SETTINGS, ctypes.byref(mode)
        )
    if not ok:
        return None
    return (int(mode.dmPositionX), int(mode.dmPositionY),
            int(mode.dmPelsWidth), int(mode.dmPelsHeight))


def capture_region(x, y, width, height):
    """Снимает область рабочего стола в настоящих пикселях -> PIL.Image."""
    if not IS_WINDOWS:
        raise RuntimeError("Снимок экрана реализован только для Windows.")

    with _RealPixels():
        screen_dc = _user32.GetDC(None)
        if not screen_dc:
            raise RuntimeError("Не удалось получить контекст экрана.")

        memory_dc = _gdi32.CreateCompatibleDC(screen_dc)
        bitmap = _gdi32.CreateCompatibleBitmap(screen_dc, width, height)
        try:
            _gdi32.SelectObject(memory_dc, bitmap)
            if not _gdi32.BitBlt(memory_dc, 0, 0, width, height,
                                 screen_dc, x, y, SRCCOPY | CAPTUREBLT):
                raise RuntimeError("Не удалось скопировать изображение экрана.")

            info = BITMAPINFO()
            info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            info.bmiHeader.biWidth = width
            info.bmiHeader.biHeight = -height   # минус — строки сверху вниз
            info.bmiHeader.biPlanes = 1
            info.bmiHeader.biBitCount = 32
            info.bmiHeader.biCompression = 0

            buffer = ctypes.create_string_buffer(width * height * 4)
            copied = _gdi32.GetDIBits(memory_dc, bitmap, 0, height, buffer,
                                      ctypes.byref(info), DIB_RGB_COLORS)
            if copied != height:
                raise RuntimeError(
                    "Прочитано %d строк изображения из %d." % (copied, height)
                )
        finally:
            _gdi32.DeleteObject(bitmap)
            _gdi32.DeleteDC(memory_dc)
            _user32.ReleaseDC(None, screen_dc)

    # GDI отдаёт BGRA
    return Image.frombuffer("RGB", (width, height), buffer, "raw", "BGRX", 0, 1)


def capture_monitor(device_name):
    """Снимает монитор целиком по его системному имени."""
    mode = display_mode(device_name)
    if mode is None:
        raise RuntimeError("Не удалось узнать режим монитора %r." % (device_name,))
    return capture_region(*mode)
