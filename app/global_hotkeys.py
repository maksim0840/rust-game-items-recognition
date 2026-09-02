"""Глобальные горячие клавиши (Windows).

Обычный фильтр событий Qt видит клавиши только когда окно программы активно,
а игра идёт в полный экран и фокус у неё. Поэтому бинды регистрируются в
системе через RegisterHotKey: Windows присылает нам WM_HOTKEY даже когда
программа свёрнута.

RegisterHotKey сообщает только о той комбинации, которую выбрал пользователь —
остальные нажатия к программе не попадают.
"""

import ctypes
import sys
from ctypes import wintypes

from PyQt5.QtCore import QAbstractNativeEventFilter, Qt
from PyQt5.QtWidgets import QApplication

IS_WINDOWS = sys.platform == "win32"

WM_HOTKEY = 0x0312

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000   # без него хоткей повторяется при удержании

# Клавиши, у которых код Qt не совпадает с виртуальным кодом Windows
SPECIAL_KEYS = {
    Qt.Key_Escape: 0x1B,
    Qt.Key_Tab: 0x09,
    Qt.Key_Backspace: 0x08,
    Qt.Key_Return: 0x0D,
    Qt.Key_Enter: 0x0D,
    Qt.Key_Insert: 0x2D,
    Qt.Key_Delete: 0x2E,
    Qt.Key_Pause: 0x13,
    Qt.Key_Print: 0x2C,
    Qt.Key_Home: 0x24,
    Qt.Key_End: 0x23,
    Qt.Key_Left: 0x25,
    Qt.Key_Up: 0x26,
    Qt.Key_Right: 0x27,
    Qt.Key_Down: 0x28,
    Qt.Key_PageUp: 0x21,
    Qt.Key_PageDown: 0x22,
    Qt.Key_CapsLock: 0x14,
    Qt.Key_NumLock: 0x90,
    Qt.Key_ScrollLock: 0x91,
}
# F1..F24 идут подряд от VK_F1
for _i in range(24):
    SPECIAL_KEYS[Qt.Key_F1 + _i] = 0x70 + _i


def modifiers_from_combo(combo):
    """Биты модификаторов Windows из сочетания Qt."""
    modifiers = MOD_NOREPEAT
    if combo & int(Qt.ControlModifier):
        modifiers |= MOD_CONTROL
    if combo & int(Qt.ShiftModifier):
        modifiers |= MOD_SHIFT
    if combo & int(Qt.AltModifier):
        modifiers |= MOD_ALT
    if combo & int(Qt.MetaModifier):
        modifiers |= MOD_WIN
    return modifiers


def virtual_key(qt_key):
    """Код клавиши Qt -> виртуальный код Windows или None.

    Запасной путь на случай, когда физический код клавиши неизвестен.
    Совпадение кодов Qt и Windows работает только для букв, цифр и пробела:
    например, Qt.Key_BracketLeft равен 0x5B, а 0x5B в Windows — это клавиша
    Windows, а не скобка. Поэтому всё остальное спрашиваем у раскладки.
    """
    vk = SPECIAL_KEYS.get(qt_key)
    if vk is not None:
        return vk
    if qt_key == Qt.Key_Space or 0x30 <= qt_key <= 0x39 or 0x41 <= qt_key <= 0x5A:
        return qt_key

    scan = ctypes.windll.user32.VkKeyScanW(ctypes.c_wchar(chr(qt_key)))
    if scan == -1:
        return None   # в текущей раскладке такого символа нет
    return scan & 0xFF


def split_combo(combo):
    """Сочетание Qt -> (флаги модификаторов Windows, виртуальный код) или None."""
    if not IS_WINDOWS or combo is None:
        return None

    key = combo & ~int(Qt.ControlModifier | Qt.ShiftModifier
                       | Qt.AltModifier | Qt.MetaModifier)
    vk = virtual_key(key)
    if vk is None:
        return None
    return modifiers_from_combo(combo), vk


class GlobalHotkeys(QAbstractNativeEventFilter):
    """Регистрирует комбинации в системе и зовёт обработчики по WM_HOTKEY."""

    def __init__(self, hwnd=None):
        super().__init__()
        self._hwnd = hwnd
        self._next_id = 1
        self._by_name = {}      # имя бинда -> id
        self._handlers = {}     # id -> обработчик
        self._installed = False

    @property
    def supported(self):
        return IS_WINDOWS

    def set_window(self, hwnd):
        """Окно, которому Windows шлёт WM_HOTKEY. Смена окна снимает биндры."""
        if hwnd == self._hwnd:
            return
        self.unregister_all()
        self._hwnd = hwnd

    def register(self, name, combo, callback, vk=None):
        """Назначает комбинацию. Возвращает True, если система её отдала.

        vk — физический код клавиши из QKeyEvent.nativeVirtualKey(). Он не
        зависит от раскладки, поэтому одна и та же клавиша работает и как "[",
        и как "х". Если его нет, код выводится из сочетания Qt.

        False означает, что комбинацию уже занял кто-то другой — например,
        другая программа или сама Windows.
        """
        self.unregister(name)
        if not IS_WINDOWS:
            return False

        if vk:
            modifiers = modifiers_from_combo(combo)
        else:
            parts = split_combo(combo)
            if parts is None:
                return False
            modifiers, vk = parts

        self._install()
        hotkey_id = self._next_id
        self._next_id += 1

        if not ctypes.windll.user32.RegisterHotKey(
            wintypes.HWND(self._hwnd) if self._hwnd else None,
            hotkey_id, modifiers, vk
        ):
            return False

        self._by_name[name] = hotkey_id
        self._handlers[hotkey_id] = callback
        return True

    def unregister(self, name):
        hotkey_id = self._by_name.pop(name, None)
        if hotkey_id is None:
            return
        self._handlers.pop(hotkey_id, None)
        if IS_WINDOWS:
            ctypes.windll.user32.UnregisterHotKey(
                wintypes.HWND(self._hwnd) if self._hwnd else None, hotkey_id
            )

    def unregister_all(self):
        for name in list(self._by_name):
            self.unregister(name)

    def _install(self):
        if self._installed:
            return
        QApplication.instance().installNativeEventFilter(self)
        self._installed = True

    def nativeEventFilter(self, event_type, message):
        if event_type != b"windows_generic_MSG":
            return False, 0

        msg = wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY:
            callback = self._handlers.get(int(msg.wParam))
            if callback is not None:
                callback()
                return True, 0
        return False, 0
