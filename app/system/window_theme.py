"""Тёмная рамка окна и иконка в панели задач (Windows).

Рамку с кнопками свернуть/закрыть рисует сама Windows, и по умолчанию она
светлая — на фоне тёмного приложения это бросается в глаза. Своя рамка тут не
нужна: достаточно попросить систему покрасить родную в тёмный, и все привычные
жесты (перетаскивание, прилипание к краям, двойной клик для разворота) остаются
работать сами собой.
"""

import ctypes
import sys
from ctypes import wintypes

IS_WINDOWS = sys.platform == "win32"

# Windows 10 версии 2004 и новее ждёт номер 20, сборки постарше — 19.
# Пробуем оба: лишний вызов ничего не портит
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19


def apply_dark_title_bar(widget):
    """Красит рамку окна в тёмный. Возвращает True, если получилось."""
    if not IS_WINDOWS:
        return False

    hwnd = int(widget.winId())
    if not hwnd:
        return False

    try:
        dwmapi = ctypes.windll.dwmapi
        dwmapi.DwmSetWindowAttribute.argtypes = [
            wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD
        ]
        enabled = ctypes.c_int(1)
        for attribute in (DWMWA_USE_IMMERSIVE_DARK_MODE,
                          DWMWA_USE_IMMERSIVE_DARK_MODE_OLD):
            dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd), attribute,
                ctypes.byref(enabled), ctypes.sizeof(enabled)
            )
        return True
    except Exception:
        # Оформление — не то, ради чего стоит ронять программу
        return False


def set_app_id(app_id):
    """Отделяет программу от python.exe в панели задач.

    Без этого Windows считает окно частью интерпретатора и показывает на панели
    задач иконку Python, а не нашу.
    """
    if not IS_WINDOWS:
        return False
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        return True
    except Exception:
        return False
