"""Главное окно: выбор предметов, слой настроек распознавания и стекло поверх игры."""

from PyQt5.QtCore import QSize, Qt, QTimer
from PyQt5.QtWidgets import QApplication, QMainWindow

from detection.pipeline import InventoryGrid, InventoryScanner, ItemRecognitionModel
from detection.items import distribute_items_into_categories, items
from system.monitors import QtMonitors
from system.window_theme import apply_dark_title_bar
from ui.game_overlay import GameOverlay
from ui.items_browser import ItemsBrowser
from ui.overlay import Overlay
from ui.scan_panel import ScanPanel


class MainWindow(QMainWindow):
    def __init__(self, game_settings=None, hide_overlay_from_capture=True):
        super().__init__()
        self.setWindowTitle("LootLens")
        self.resize(1400, 760)

        # Настройки игры, подтверждённые в стартовом окне
        self.game_settings = game_settings or {}

        # Ставится, когда пользователь просит вернуться к настройкам:
        # main() смотрит на него после закрытия окна
        self.reopen_settings = False

        # Координаты последнего распознавания
        self.last_scan = None

        # Размер окна в логических пикселях. При переезде на монитор с другим
        # масштабом Qt пересчитывает геометрию по-своему, и окно скачет —
        # поэтому запоминаем задуманный размер и восстанавливаем его
        self._logical_size = self.size()
        self._logical_ratio = self.devicePixelRatioF()
        self._adjusting_geometry = False
        self._watched_window = None

        categories = distribute_items_into_categories(items)

        self.items_browser = ItemsBrowser(categories, self)
        self.setCentralWidget(self.items_browser)

        # Полупрозрачный слой поверх окна приложения: скрыт, пока не вызван show_overlay()
        self.app_overlay = Overlay(self)
        self.items_browser.select_requested.connect(self.app_overlay.show_overlay)
        self.items_browser.settings_requested.connect(self.back_to_settings)

        # Панель управления распознаванием живёт внутри полупрозрачного слоя
        self.scan_panel = ScanPanel(self.app_overlay)
        self.scan_panel.scan_requested.connect(self.run_scan)
        self.scan_panel.clear_requested.connect(self.clear_scan)
        self.scan_panel.display_changed.connect(self.apply_display_flags)
        self.scan_panel.close_requested.connect(self.app_overlay.hide_overlay)
        self.app_overlay.set_content(self.scan_panel)

        # Прозрачное окно поверх игры: живёт ровно столько же, сколько панель
        self.game_overlay = GameOverlay(
            QtMonitors.screen_for(self.game_settings.get("screen_name")),
            hide_from_capture=hide_overlay_from_capture,
        )
        self.app_overlay.opened.connect(self.game_overlay.show_overlay)
        self.app_overlay.closed.connect(self.game_overlay.hide_overlay)

        # Модель весит 112 МБ, поэтому создаём сканер при первом запуске,
        # а не при открытии окна
        self.scanner = None

    def _ensure_scanner(self):
        if self.scanner is None:
            self.scan_panel.set_status("Загружается модель распознавания…")
            QApplication.processEvents()
            self.scanner = InventoryScanner.from_settings(
                InventoryGrid(), ItemRecognitionModel(), self.game_settings
            )
        return self.scanner

    def run_scan(self):
        """Снимает экран и считает, сколько выбранных предметов на нём нашлось."""
        labels = set(self.items_browser.selected_labels())
        if not labels:
            self.scan_panel.set_status(
                "Не выбрано ни одного предмета — закройте панель и отметьте нужные"
            )
            return

        # Старые квадраты убираем до снимка: они и устарели, и не должны
        # попасть в кадр, даже если исключение из захвата не сработало
        self.clear_scan()
        QApplication.processEvents()

        try:
            scanner = self._ensure_scanner()
            self.scan_panel.set_status("Распознавание…")
            QApplication.processEvents()

            screenshot = scanner.make_screenshot()
            matched, undefined, not_matched = scanner.find_classes_on_screenshot(
                screenshot, labels
            )
        except Exception as exc:
            # Съехавшее разрешение, отключённый монитор, сбой модели — что угодно
            # из этого не должно ронять приложение прямо во время игры
            self.scan_panel.set_status(str(exc))
            return

        self.last_scan = (matched, undefined, not_matched)
        self.scan_panel.set_results(len(matched), len(undefined), len(not_matched))

        self.apply_display_flags()
        self.game_overlay.set_boxes(matched, undefined, not_matched)

    def clear_scan(self):
        self.last_scan = None
        self.scan_panel.clear_results()
        self.game_overlay.clear_boxes()

    def apply_display_flags(self):
        """Флажки панели управляют и строками счётчиков, и квадратами на экране."""
        matched, undefined, not_matched = self.scan_panel.display_flags()
        self.game_overlay.set_visible_groups(matched, undefined, not_matched)

    # --- размер окна при переезде между мониторами ------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        # Рамку с кнопками рисует Windows, и по умолчанию она светлая
        apply_dark_title_bar(self)
        handle = self.windowHandle()
        if handle is not None and handle is not self._watched_window:
            self._watched_window = handle
            handle.screenChanged.connect(self._on_screen_changed)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Запоминаем только то, что изменил пользователь. Пересчёт из-за
        # переезда на монитор с другим масштабом приходит с новым DPR —
        # такой размер запоминать нельзя, иначе он подменит задуманный
        if self._adjusting_geometry or self.devicePixelRatioF() != self._logical_ratio:
            return
        self._logical_size = event.size()

    def _on_screen_changed(self, screen):
        """Возвращает окну прежний логический размер на новом мониторе.

        В момент сигнала размер ещё старый — Qt пересчитает его сразу после.
        Поэтому не правим ничего здесь, а становимся в очередь следом за ним.
        """
        target = self._logical_size
        if screen is not None:
            # Не больше, чем помещается на новом экране
            available = screen.availableGeometry().size()
            target = QSize(
                min(target.width(), available.width()),
                min(target.height(), available.height()),
            )

        self._adjusting_geometry = True
        QTimer.singleShot(0, lambda: self._finish_geometry_fix(target))

    def _finish_geometry_fix(self, target):
        if self.size() != target:
            self.resize(target)
        self._logical_size = target
        self._logical_ratio = self.devicePixelRatioF()
        self._adjusting_geometry = False

    def back_to_settings(self):
        """Закрывает окно; main() увидит флаг и снова покажет настройки."""
        self.reopen_settings = True
        self.close()

