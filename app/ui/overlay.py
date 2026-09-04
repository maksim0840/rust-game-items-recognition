from PyQt5.QtCore import QEvent, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QApplication, QFrame, QHBoxLayout, QVBoxLayout, QWidget


class Overlay(QWidget):
    """Полупрозрачный слой поверх окна-родителя.

    Полностью перекрывает родителя, блокирует мышь и клавиатуру для всего,
    что под ним, и служит контейнером для собственных виджетов.

    Использование:
        overlay = Overlay(main_window)
        overlay.set_content(my_widget)
        overlay.show_overlay()
        ...
        overlay.hide_overlay()
    """

    opened = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, parent, dim_color=QColor(0, 0, 0, 170), close_on_esc=True,
                 close_on_click_outside=False):
        super().__init__(parent)
        self.setObjectName("overlay")

        self._dim_color = QColor(dim_color)
        self._close_on_esc = close_on_esc
        self._close_on_click_outside = close_on_click_outside
        self._content = None

        # Ловим мышь на себя и не пропускаем её к тому, что снизу
        self.setAttribute(Qt.WA_NoMousePropagation, True)
        self.setFocusPolicy(Qt.StrongFocus)

        # Панель по центру, куда кладётся полезное содержимое
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.addStretch(1)

        middle = QHBoxLayout()
        middle.addStretch(1)

        self.panel = QFrame(self)
        self.panel.setObjectName("overlayPanel")
        self.panel.hide()  # пустая панель не должна висеть рамкой посреди экрана
        self.panel_layout = QVBoxLayout(self.panel)
        self.panel_layout.setContentsMargins(24, 24, 24, 24)
        self.panel_layout.setSpacing(16)
        middle.addWidget(self.panel, 0)

        middle.addStretch(1)
        root.addLayout(middle, 0)
        root.addStretch(1)

        # Следим за размером родителя, чтобы слой всегда перекрывал его целиком
        parent.installEventFilter(self)
        self.setGeometry(parent.rect())
        self.hide()

    # --- содержимое ------------------------------------------------------------

    def set_content(self, widget):
        """Помещает виджет в центральную панель слоя."""
        if self._content is not None:
            self.panel_layout.removeWidget(self._content)
            self._content.setParent(None)
        self._content = widget
        if widget is not None:
            self.panel_layout.addWidget(widget)
        self.panel.setVisible(widget is not None)

    # --- показ и скрытие -------------------------------------------------------

    def show_overlay(self):
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.setFocus(Qt.OtherFocusReason)
        # Пока слой открыт, перехватываем клавиатуру у всего приложения
        QApplication.instance().installEventFilter(self)
        self.opened.emit()

    def hide_overlay(self):
        QApplication.instance().removeEventFilter(self)
        self.hide()
        self.closed.emit()

    def toggle_overlay(self):
        if self.isVisible():
            self.hide_overlay()
        else:
            self.show_overlay()

    # --- перекрытие и блокировка ----------------------------------------------

    def eventFilter(self, obj, event):
        # Родитель изменил размер — растягиваемся следом
        if obj is self.parentWidget() and event.type() == QEvent.Resize:
            self.setGeometry(self.parentWidget().rect())
            return False

        # Клавиатура и горячие клавиши не должны доходить до виджетов под слоем
        if self.isVisible() and event.type() in (
            QEvent.KeyPress,
            QEvent.KeyRelease,
            QEvent.ShortcutOverride,
            QEvent.Shortcut,
        ):
            if isinstance(obj, QWidget) and obj is not self and not self.isAncestorOf(obj):
                event.accept()
                return True

        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._dim_color)

    def mousePressEvent(self, event):
        # Съедаем клик: до окна под слоем он не дойдёт
        if self._close_on_click_outside and not self.panel.geometry().contains(event.pos()):
            self.hide_overlay()
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    def wheelEvent(self, event):
        # Иначе колесо ушло бы к родителю и прокрутило список под слоем
        event.accept()

    def keyPressEvent(self, event):
        if self._close_on_esc and event.key() == Qt.Key_Escape:
            self.hide_overlay()
            return
        event.accept()
