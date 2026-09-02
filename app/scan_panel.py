from PyQt5.QtCore import QEvent, Qt, pyqtSignal

from global_hotkeys import GlobalHotkeys
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Клавиши-модификаторы сами по себе биндом быть не могут
MODIFIER_KEYS = {Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta,
                 Qt.Key_AltGr, Qt.Key_CapsLock, Qt.Key_NumLock, Qt.Key_ScrollLock}

TRACKED_MODIFIERS = (Qt.ControlModifier | Qt.ShiftModifier
                     | Qt.AltModifier | Qt.MetaModifier)


def combo_from_event(event):
    """Сочетание клавиш из события: код клавиши плюс биты модификаторов."""
    return int(event.modifiers() & TRACKED_MODIFIERS) | int(event.key())


class KeyBindButton(QPushButton):
    """Поле бинда: клик — ждём клавишу, повторный клик по крестику — сброс."""

    EMPTY_TEXT = "Не назначено"
    CAPTURE_TEXT = "Нажмите клавишу…"

    bind_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("bindButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(False)
        self.setFocusPolicy(Qt.StrongFocus)

        self._combo = None
        self._vk = None        # физический код клавиши, не зависит от раскладки
        self._capturing = False
        self._refresh_text()

        self.clicked.connect(self.start_capture)

    @property
    def combo(self):
        return self._combo

    @property
    def native_vk(self):
        return self._vk

    @property
    def is_capturing(self):
        return self._capturing

    def start_capture(self):
        if self._capturing:
            return
        self._capturing = True

        # Старый бинд стирается сразу, а не после выбора нового. Иначе он
        # продолжал бы работать во время выбора, а назначить ту же клавишу
        # заново было бы нельзя: система перехватывала бы её до нас
        had_bind = self._combo is not None
        self._combo = None
        self._vk = None

        self.setProperty("capturing", "true")
        self._repolish()
        self._refresh_text()
        self.setFocus(Qt.OtherFocusReason)
        # Перехватываем клавиатуру, чтобы бинд не улетел другому виджету
        self.grabKeyboard()

        if had_bind:
            # Панель по этому сигналу снимет системную регистрацию
            self.bind_changed.emit()

    def cancel_capture(self):
        if not self._capturing:
            return
        self._capturing = False
        self.releaseKeyboard()
        self.setProperty("capturing", "false")
        self._repolish()
        self._refresh_text()

    def clear_bind(self):
        self.cancel_capture()
        if self._combo is not None:
            self._combo = None
            self._vk = None
            self._refresh_text()
            self.bind_changed.emit()

    def matches(self, event):
        if self._combo is None:
            return False
        # Сравниваем по физической клавише: на другой раскладке та же клавиша
        # даёт другой символ, но код остаётся прежним
        if self._vk and event.nativeVirtualKey():
            same_key = event.nativeVirtualKey() == self._vk
            same_mods = (int(event.modifiers() & TRACKED_MODIFIERS)
                         == self._combo & int(TRACKED_MODIFIERS))
            return same_key and same_mods
        return combo_from_event(event) == self._combo

    def keyPressEvent(self, event):
        if not self._capturing:
            super().keyPressEvent(event)
            return

        key = event.key()
        if key in MODIFIER_KEYS:
            return  # ждём обычную клавишу вместе с зажатым модификатором
        if key == Qt.Key_Escape:
            self.cancel_capture()
            return

        self._combo = combo_from_event(event)
        self._vk = event.nativeVirtualKey() or None
        self._capturing = False
        self.releaseKeyboard()
        self.setProperty("capturing", "false")
        self._repolish()
        self._refresh_text()
        self.bind_changed.emit()

    def focusOutEvent(self, event):
        self.cancel_capture()
        super().focusOutEvent(event)

    def _refresh_text(self):
        if self._capturing:
            self.setText(self.CAPTURE_TEXT)
        elif self._combo is None:
            self.setText(self.EMPTY_TEXT)
        else:
            self.setText(QKeySequence(self._combo).toString())

    def _repolish(self):
        self.style().unpolish(self)
        self.style().polish(self)


class ScanPanel(QWidget):
    """Управление распознаванием: что показывать, биндыи результат."""

    scan_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    close_requested = pyqtSignal()
    display_changed = pyqtSignal()   # переключили флажки «что показывать»

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("scanPanel")
        # Хватает, чтобы самая длинная строка результата шла одной строкой
        self.setMinimumWidth(470)

        self._results = None   # (matched, undefined, not_matched) последнего прогона

        # Биндры регистрируются в системе, иначе они не сработают, пока
        # программа свёрнута, а игра занимает весь экран
        self.hotkeys = GlobalHotkeys()
        self._global_binds = set()   # какие биндры система реально отдала
        self._hotkey_warning = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel("Распознавание предметов", self)
        title.setObjectName("scanTitle")
        header.addWidget(title)
        header.addStretch(1)

        self.close_button = QPushButton("✕", self)
        self.close_button.setObjectName("panelClose")
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setFixedSize(28, 28)
        self.close_button.setToolTip("Закрыть панель (Esc)")
        self.close_button.clicked.connect(self.close_requested)
        header.addWidget(self.close_button, 0, Qt.AlignTop)

        root.addLayout(header)

        # --- что показывать ----------------------------------------------------

        root.addWidget(self._section("Что показывать"))

        self.show_matched_check = self._result_check("Найденные предметы")
        self.show_undefined_check = self._result_check("Нераспознанные предметы")
        self.show_not_matched_check = self._result_check("Не те предметы, что запрашивались")
        for check in (self.show_matched_check, self.show_undefined_check,
                      self.show_not_matched_check):
            root.addWidget(check)

        # --- биндры ------------------------------------------------------------

        root.addWidget(self._section("Горячие клавиши"))

        self.scan_bind = KeyBindButton(self)
        self.clear_bind = KeyBindButton(self)
        # Подсказка внизу называет текущую клавишу запуска — при смене бинда
        # её нужно перерисовать
        self.scan_bind.bind_changed.connect(self._refresh_results)
        self.scan_bind.bind_changed.connect(self._apply_hotkeys)
        self.clear_bind.bind_changed.connect(self._apply_hotkeys)
        root.addLayout(self._bind_row("Запустить распознавание", self.scan_bind))
        root.addLayout(self._bind_row("Очистить результат", self.clear_bind))

        # --- результат ---------------------------------------------------------

        separator = QFrame(self)
        separator.setObjectName("scanSeparator")
        separator.setFrameShape(QFrame.HLine)
        root.addWidget(separator)

        self.matched_label = QLabel("", self)
        self.matched_label.setObjectName("resultMatched")
        self.undefined_label = QLabel("", self)
        self.undefined_label.setObjectName("resultUndefined")
        self.not_matched_label = QLabel("", self)
        self.not_matched_label.setObjectName("resultNotMatched")
        for label in (self.matched_label, self.undefined_label, self.not_matched_label):
            label.setWordWrap(True)
            root.addWidget(label)

        self.status_label = QLabel("", self)
        self.status_label.setObjectName("scanStatus")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.clear_results()

        # Бинды слушаем на уровне приложения: сработать они должны независимо
        # от того, на каком виджете внутри слоя сейчас фокус
        QApplication.instance().installEventFilter(self)

    # --- сборка мелких блоков --------------------------------------------------

    def _section(self, text):
        label = QLabel(text, self)
        label.setObjectName("scanSection")
        return label

    def _result_check(self, text):
        check = QCheckBox(text, self)
        check.setObjectName("scanCheck")
        check.setCursor(Qt.PointingHandCursor)
        check.setChecked(True)
        check.toggled.connect(self._refresh_results)
        check.toggled.connect(self.display_changed)
        return check

    def _bind_row(self, text, bind_button):
        row = QHBoxLayout()
        row.setSpacing(8)

        label = QLabel(text, self)
        label.setObjectName("scanLabel")
        label.setFixedWidth(210)
        row.addWidget(label)

        bind_button.setFixedWidth(150)
        row.addWidget(bind_button)

        reset = QPushButton("✕", self)
        reset.setObjectName("bindReset")
        reset.setCursor(Qt.PointingHandCursor)
        reset.setFixedWidth(30)
        reset.setToolTip("Сбросить бинд")
        reset.clicked.connect(bind_button.clear_bind)
        row.addWidget(reset)

        row.addStretch(1)
        return row

    # --- результат -------------------------------------------------------------

    def set_results(self, matched, undefined, not_matched):
        self._results = (matched, undefined, not_matched)
        self.status_label.setText("")
        self._refresh_results()

    def clear_results(self):
        self._results = None
        self._refresh_results()

    def set_status(self, text):
        self.status_label.setText(text)

    def display_flags(self):
        """Какие группы результата пользователь хочет видеть."""
        return (
            self.show_matched_check.isChecked(),
            self.show_undefined_check.isChecked(),
            self.show_not_matched_check.isChecked(),
        )

    def _refresh_results(self):
        rows = (
            (self.show_matched_check, self.matched_label, "Найдено предметов: %d"),
            (self.show_undefined_check, self.undefined_label, "Нераспознано предметов: %d"),
            (self.show_not_matched_check, self.not_matched_label,
             "Найдено не тех предметов, которые запрашивались: %d"),
        )
        for index, (check, label, template) in enumerate(rows):
            visible = check.isChecked() and self._results is not None
            label.setVisible(visible)
            if visible:
                label.setText(template % self._results[index])

        if self._results is None:
            self.status_label.setText(self._hotkey_warning or self._hint())

    def _hint(self):
        if self.scan_bind.combo is None:
            return "Назначьте клавишу запуска, чтобы распознать предметы"
        return "Нажмите %s, чтобы распознать предметы" % (
            QKeySequence(self.scan_bind.combo).toString(),
        )

    # --- горячие клавиши -------------------------------------------------------

    def _apply_hotkeys(self):
        """Перерегистрирует биндры в системе под текущие сочетания."""
        if not self.isVisible():
            self.hotkeys.unregister_all()
            self._global_binds.clear()
            return

        self.hotkeys.set_window(int(self.window().winId()))
        self._global_binds.clear()
        busy = []

        for name, button, callback in (
            ("scan", self.scan_bind, self.scan_requested.emit),
            ("clear", self.clear_bind, self.clear_requested.emit),
        ):
            self.hotkeys.unregister(name)
            if button.combo is None:
                continue
            if self.hotkeys.register(name, button.combo, callback,
                                     vk=button.native_vk):
                self._global_binds.add(name)
            elif self.hotkeys.supported:
                busy.append(QKeySequence(button.combo).toString())

        if busy:
            self._hotkey_warning = (
                "%s уже занята другой программой — вне окна она не сработает"
                % ", ".join(busy)
            )
        else:
            self._hotkey_warning = ""
        if self._results is None:
            self.status_label.setText(self._hotkey_warning or self._hint())

    def showEvent(self, event):
        super().showEvent(event)
        # spontaneous — это разворачивание окна системой, биндры при этом
        # никуда не девались и перерегистрировать их не нужно
        if not event.spontaneous():
            self._apply_hotkeys()

    def eventFilter(self, obj, event):
        # Запасной путь: пока сочетание не занято системным биндом, ловим его
        # обычным способом. Зарегистрированную комбинацию Windows забирает
        # себе и до Qt она не доходит, так что двойного срабатывания нет
        if event.type() == QEvent.KeyPress and self.isVisible():
            # Пока назначается бинд, он не должен сам себя запускать
            capturing = self.scan_bind.is_capturing or self.clear_bind.is_capturing
            if not capturing and not event.isAutoRepeat():
                if "scan" not in self._global_binds and self.scan_bind.matches(event):
                    self.scan_requested.emit()
                    return True
                if "clear" not in self._global_binds and self.clear_bind.matches(event):
                    self.clear_requested.emit()
                    return True
        return super().eventFilter(obj, event)

    def hideEvent(self, event):
        # Сворачивание окна тоже присылает hideEvent, но с spontaneous=True —
        # именно ради свёрнутого окна биндры и делались, снимать их нельзя
        if event.spontaneous():
            super().hideEvent(event)
            return

        self.scan_bind.cancel_capture()
        self.clear_bind.cancel_capture()
        # Панель закрыта — отпускаем клавиши, иначе они остались бы отнятыми
        # у игры и остальных программ
        self.hotkeys.unregister_all()
        self._global_binds.clear()
        super().hideEvent(event)
