"""Прозрачное окно поверх игры.

"Стекло" на весь монитор: без рамки и фона, поверх всех окон, полностью
прозрачное для мыши и клавиатуры. Игра о нём не знает — фокус не забирается,
клики проходят насквозь.

Единственное, что оно делает, — рисует полупрозрачные квадраты по координатам
ячеек, которые вернуло распознавание.
"""

import ctypes
import sys

from PyQt5.QtCore import QRect, Qt, QTimer
from PyQt5.QtGui import QBrush, QColor, QPainter, QPen
from PyQt5.QtWidgets import QApplication, QWidget

from system.screen_capture import display_mode

IS_WINDOWS = sys.platform == "win32"

# Окно остаётся видимым на экране, но пропадает из любого захвата: иначе
# наши же квадраты попали бы в следующий скриншот и модель распознавала бы их
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000

WDA_NONE = 0x00
WDA_MONITOR = 0x01              # окно попадает в захват чёрным прямоугольником
WDA_EXCLUDEFROMCAPTURE = 0x11   # Windows 10 2004 и новее

# Как часто заново заявлять себя поверх остальных окон
TOPMOST_INTERVAL_MS = 2000

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
HWND_TOPMOST = -1

# Цвета групп: те же, что у строк результата в панели
GROUP_COLORS = {
    "matched": QColor(158, 194, 74),      # найденные предметы
    "undefined": QColor(194, 160, 74),    # нераспознанные
    "not_matched": QColor(183, 194, 191),  # не те, что запрашивались
}
FILL_ALPHA = 70
BORDER_ALPHA = 220
BORDER_WIDTH = 2


class GameOverlay(QWidget):
    """Полноэкранное прозрачное окно поверх игры."""

    def __init__(self, screen=None, parent=None, hide_from_capture=True):
        """hide_from_capture=False делает квадраты видимыми для записи экрана."""
        super().__init__(parent)
        self.setObjectName("gameOverlay")

        self._hide_from_capture = hide_from_capture
        self._screen = screen
        self._boxes = {"matched": [], "undefined": [], "not_matched": []}
        self._visible_groups = {"matched": True, "undefined": True, "not_matched": True}
        self._capture_excluded = False

        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint          # без рамки и заголовка
            | Qt.WindowStaysOnTopHint         # поверх остальных окон
            | Qt.Tool                         # не показывать в Alt+Tab и на панели задач
            | Qt.WindowTransparentForInput    # мышь проходит насквозь
            | Qt.WindowDoesNotAcceptFocus     # не забирать фокус у игры
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        # Без этого Qt при показе попытается активировать окно, и полноэкранная
        # игра свернётся
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        # Другая программа могла перебить нас в своём topmost — заявляем себя снова
        self._topmost_timer = QTimer(self)
        self._topmost_timer.setInterval(TOPMOST_INTERVAL_MS)
        self._topmost_timer.timeout.connect(self._reassert_topmost)

    # --- показ и скрытие -------------------------------------------------------

    def set_screen(self, screen):
        self._screen = screen
        if self.isVisible():
            self._fit_to_screen()

    def show_overlay(self, screen=None):
        if screen is not None:
            self._screen = screen
        self._fit_to_screen()
        self.show()
        self._force_noactivate()
        self._exclude_from_capture()
        self._reassert_topmost()
        self._topmost_timer.start()

    def hide_overlay(self):
        self._topmost_timer.stop()
        self.clear_boxes()
        self.hide()

    def _fit_to_screen(self):
        screen = self._screen or QApplication.instance().primaryScreen()
        if screen is None:
            return
        self.setGeometry(screen.geometry())

    # --- что рисуем ------------------------------------------------------------

    def set_boxes(self, matched=(), undefined=(), not_matched=()):
        """Координаты ячеек в пикселях снимка экрана."""
        self._boxes = {
            "matched": list(matched),
            "undefined": list(undefined),
            "not_matched": list(not_matched),
        }
        self.update()

    def clear_boxes(self):
        self._boxes = {"matched": [], "undefined": [], "not_matched": []}
        self.update()

    def set_visible_groups(self, matched=True, undefined=True, not_matched=True):
        """Какие группы показывать — по флажкам из панели распознавания."""
        self._visible_groups = {
            "matched": matched,
            "undefined": undefined,
            "not_matched": not_matched,
        }
        self.update()

    def has_boxes(self):
        return any(self._boxes.values())

    # --- отрисовка -------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)

        # Снимок сделан в настоящих пикселях монитора, а окно живёт в
        # координатах Qt. Коэффициент считаем по факту: ширина окна против
        # настоящей ширины монитора — devicePixelRatio для этого не годится,
        # он зависит от режима DPI-осведомлённости процесса
        ratio = 1.0 / self._paint_scale()

        for group, boxes in self._boxes.items():
            if not boxes or not self._visible_groups.get(group, True):
                continue

            color = GROUP_COLORS[group]
            fill = QColor(color)
            fill.setAlpha(FILL_ALPHA)
            border = QColor(color)
            border.setAlpha(BORDER_ALPHA)

            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(border, BORDER_WIDTH))

            for x1, y1, x2, y2 in boxes:
                rect = QRect(
                    int(x1 / ratio), int(y1 / ratio),
                    int((x2 - x1) / ratio), int((y2 - y1) / ratio),
                )
                painter.drawRect(rect)

    def _paint_scale(self):
        """Во сколько координат окна укладывается один настоящий пиксель."""
        screen = self._screen or self.screen()
        if screen is None or not self.width():
            return 1.0
        mode = display_mode(screen.name())
        if mode is None or not mode[2]:
            return 1.0
        return self.width() / mode[2]

    # --- системные мелочи ------------------------------------------------------

    def _hwnd(self):
        return int(self.winId()) if IS_WINDOWS else None

    def _force_noactivate(self):
        """Дожимает WS_EX_NOACTIVATE: Qt по флагу окна его не выставляет.

        Без этого стиля окно теоретически может стать активным и увести
        фокус у игры — а полноэкранная игра при потере фокуса сворачивается.
        """
        if not IS_WINDOWS:
            return
        hwnd = self._hwnd()
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if not style & WS_EX_NOACTIVATE:
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE
            )

    def set_hide_from_capture(self, enabled):
        """Переключает невидимость для записи экрана прямо на ходу."""
        if enabled == self._hide_from_capture:
            return
        self._hide_from_capture = enabled
        self._capture_excluded = False
        if self.isVisible():
            self._exclude_from_capture()

    def _exclude_from_capture(self):
        """Прячет окно от скриншотов, оставляя видимым на экране.

        Нужно, чтобы наши же квадраты не попали в следующий снимок и модель
        не пыталась их распознать. Обратная сторона: окно не видно ни в OBS,
        ни на скриншотах — для записи ролика защиту надо снять.
        """
        if not IS_WINDOWS:
            return
        hwnd = self._hwnd()
        set_affinity = ctypes.windll.user32.SetWindowDisplayAffinity

        if not self._hide_from_capture:
            set_affinity(hwnd, WDA_NONE)
            self._capture_excluded = False
            return

        if self._capture_excluded:
            return
        if set_affinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
            self._capture_excluded = True
        elif set_affinity(hwnd, WDA_MONITOR):
            # На старых сборках Windows окно попадёт в захват чёрным
            # прямоугольником — хуже, но модель хотя бы не увидит свои квадраты
            self._capture_excluded = True

    def _reassert_topmost(self):
        if not IS_WINDOWS or not self.isVisible():
            return
        ctypes.windll.user32.SetWindowPos(
            self._hwnd(), HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )
