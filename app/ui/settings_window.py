from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from system.monitors import QtMonitors
from system.window_theme import apply_dark_title_bar

UI_SCALE_MIN = 0.50
UI_SCALE_MAX = 1.00
UI_SCALE_STEP = 0.01

RESOLUTION_MIN = 640, 480
RESOLUTION_MAX = 15360, 8640


def _build_labels(screens):
    """Достраивает подписи для списка: модель монитора, а если её нет — номер.

    Работает поверх данных от QtMonitors: сами данные языконезависимы,
    а формулировки нужны только этому окну.
    """
    # Одинаковые модели встречаются часто (два одинаковых монитора),
    # поэтому такие подписи дополняем номером
    duplicates = {
        screen["model"]
        for screen in screens
        if screen["model"] and sum(1 for s in screens if s["model"] == screen["model"]) > 1
    }

    for screen in screens:
        if screen["model"]:
            title = screen["model"]
            if screen["model"] in duplicates:
                title += " (монитор %s)" % screen["number"]
        else:
            title = "Монитор %s" % screen["number"]

        label = "%s — %d × %d" % (title, screen["width"], screen["height"])
        if screen["primary"]:
            label += " (основной)"
        screen["label"] = label


class SettingsDialog(QDialog):
    """Окно с настройками игры, которое открывается перед выбором предметов.

    Значения нужно указать такими же, какие стоят в самой игре Rust —
    от них зависит, как предметы выглядят на скриншоте инвентаря.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LootLens — настройки")
        self.setObjectName("settingsDialog")
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        title = QLabel("Настройки игры", self)
        title.setObjectName("settingsTitle")
        root.addWidget(title)

        hint = QLabel(
            "Укажите значения так же, как они выставлены в Rust —\n"
            "от них зависит размер и положение предметов в игре.",
            self,
        )
        hint.setObjectName("settingsHint")
        root.addWidget(hint)

        # --- Интерфейс ---------------------------------------------------------

        interface_header = QLabel("Интерфейс", self)
        interface_header.setObjectName("settingsSection")
        root.addWidget(interface_header)

        scale_row = QHBoxLayout()
        scale_row.setSpacing(8)
        scale_row.addWidget(self._field_label("Масштаб интерфейса"))

        self.ui_scale_spin = QDoubleSpinBox(self)
        self.ui_scale_spin.setObjectName("settingsInput")
        self.ui_scale_spin.setDecimals(2)
        self.ui_scale_spin.setRange(UI_SCALE_MIN, UI_SCALE_MAX)
        self.ui_scale_spin.setSingleStep(UI_SCALE_STEP)
        self.ui_scale_spin.setValue(UI_SCALE_MAX)

        scale_row.addWidget(self.ui_scale_spin)
        scale_row.addStretch(1)
        root.addLayout(scale_row)

        scale_path = QLabel("В игре: Options → User Interface → User Interface Scale", self)
        scale_path.setObjectName("settingsPath")
        root.addWidget(scale_path)

        # --- Экран -------------------------------------------------------------

        screen_header = QLabel("Экран", self)
        screen_header.setObjectName("settingsSection")
        root.addWidget(screen_header)

        monitor_row = QHBoxLayout()
        monitor_row.setSpacing(8)
        monitor_row.addWidget(self._field_label("Монитор для игры"))

        self.monitor_combo = QComboBox(self)
        self.monitor_combo.setObjectName("settingsCombo")
        self.monitor_combo.setCursor(Qt.PointingHandCursor)
        self.monitor_combo.setToolTip("Монитор, на котором запускается Rust")
        monitor_row.addWidget(self.monitor_combo, 1)
        root.addLayout(monitor_row)

        monitor_hint = QLabel(
            "Разрешение подставится по выбранному монитору",
            self,
        )
        monitor_hint.setObjectName("settingsPath")
        root.addWidget(monitor_hint)

        resolution_row = QHBoxLayout()
        resolution_row.setSpacing(8)
        resolution_row.addWidget(self._field_label("Разрешение экрана"))

        self.width_spin = QSpinBox(self)
        self.width_spin.setObjectName("settingsInput")
        self.width_spin.setRange(RESOLUTION_MIN[0], RESOLUTION_MAX[0])
        self.width_spin.setSuffix(" px")
        # Разрешение в игре обязано совпадать с разрешением монитора,
        # поэтому значение только показывается, а не вводится
        self.width_spin.setEnabled(False)
        resolution_row.addWidget(self.width_spin)

        separator = QLabel("×", self)
        separator.setObjectName("settingsTimes")
        resolution_row.addWidget(separator)

        self.height_spin = QSpinBox(self)
        self.height_spin.setObjectName("settingsInput")
        self.height_spin.setRange(RESOLUTION_MIN[1], RESOLUTION_MAX[1])
        self.height_spin.setSuffix(" px")
        self.height_spin.setEnabled(False)
        resolution_row.addWidget(self.height_spin)

        resolution_row.addStretch(1)
        root.addLayout(resolution_row)

        resolution_path = QLabel(
            "В игре должно стоять то же разрешение, что и у монитора: "
            "Options → Screen → Resolution",
            self,
        )
        resolution_path.setObjectName("settingsNote")
        resolution_path.setWordWrap(True)
        root.addWidget(resolution_path)

        # Полноэкранный режим пока единственный поддерживаемый, поэтому
        # галочка стоит всегда и снять её нельзя
        self.fullscreen_check = QCheckBox("Полноэкранный режим", self)
        self.fullscreen_check.setObjectName("settingsCheck")
        self.fullscreen_check.setChecked(True)
        self.fullscreen_check.setEnabled(False)
        root.addWidget(self.fullscreen_check)

        fullscreen_note = QLabel(
            "Программа работает только с полноэкранным режимом:"
            " Options → Screen → Screen Mode",
            self,
        )
        fullscreen_note.setObjectName("settingsNote")
        fullscreen_note.setWordWrap(True)
        root.addWidget(fullscreen_note)

        root.addSpacing(6)

        self.confirm_button = QPushButton("Подтвердить настройки", self)
        self.confirm_button.setObjectName("confirmButton")
        self.confirm_button.setCursor(Qt.PointingHandCursor)
        self.confirm_button.setDefault(True)
        self.confirm_button.clicked.connect(self.accept)
        root.addWidget(self.confirm_button)

        self.setFixedWidth(500)

        self.monitors = QtMonitors()
        self._populate_monitors()
        self.monitor_combo.currentIndexChanged.connect(self._on_monitor_changed)

        # Монитор могли подключить или отключить, пока окно открыто
        app = QApplication.instance()
        app.screenAdded.connect(self._populate_monitors)
        app.screenRemoved.connect(self._populate_monitors)

    # --- мониторы --------------------------------------------------------------

    def _populate_monitors(self, *_args):
        """Заполняет список мониторов, сохраняя текущий выбор, если он ещё существует."""
        selected = self.monitor_combo.currentData()

        # Список могли позвать из-за подключения монитора — названия перечитываем
        self.monitors.refresh()
        screens = self.monitors.all()
        _build_labels(screens)

        self.monitor_combo.blockSignals(True)
        self.monitor_combo.clear()
        for screen in screens:
            # Храним имя, а не QScreen: при отключении монитора объект удаляется
            self.monitor_combo.addItem(screen["label"], screen["name"])
        index = self.monitor_combo.findData(selected)
        self.monitor_combo.setCurrentIndex(max(index, 0))
        self.monitor_combo.blockSignals(False)

        if index < 0:
            # Выбранного монитора больше нет (или это первое заполнение) —
            # подставляем разрешение того, что выбрался вместо него
            self._on_monitor_changed()

    def _on_monitor_changed(self, *_args):
        screen = self.monitors.find(self.monitor_combo.currentData())
        if screen is not None:
            self.width_spin.setValue(screen["width"])
            self.height_spin.setValue(screen["height"])

    def showEvent(self, event):
        super().showEvent(event)
        # Рамку с кнопками рисует Windows, и по умолчанию она светлая
        apply_dark_title_bar(self)

    def _field_label(self, text):
        label = QLabel(text, self)
        label.setObjectName("settingsLabel")
        label.setFixedWidth(150)  # общая ширина колонки, чтобы поля были на одной линии
        return label

    def settings(self):
        """Значения, выбранные пользователем."""
        return {
            "ui_scale": round(self.ui_scale_spin.value(), 2),
            "fullscreen": self.fullscreen_check.isChecked(),
            "width": self.width_spin.value(),
            "height": self.height_spin.value(),
            "screen_name": self.monitor_combo.currentData(),
            "screen_index": self.monitor_combo.currentIndex(),
        }
