from PIL import Image

from PyQt5.QtCore import QPoint, QRect, QSize, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QFont, QFontMetrics, QImage, QPixmap
from PyQt5.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

ALL_CATEGORY = "All"

ICON_SIZE = 144
CARD_WIDTH = 198
CARD_HEIGHT = 225
CARD_SPACING = 9
CHECK_SIZE = 26

# Ширина боковых элементов верхней панели: кнопка настроек и поиск
SIDE_WIDTH = 180

# Иконки подгружаются лениво: 512x512 RGBA * 1200 предметов не помещаются в память,
# поэтому декодируем только то, что реально попало в видимую область.
_pixmap_cache = {}


def item_pixmap(item, ratio=1.0):
    """Готовит QPixmap-иконку предмета из его PIL-изображения (с кэшированием).

    ratio — масштаб монитора. Эскиз рисуется в реальных пикселях экрана
    (144 логических на мониторе со 150% — это 216 настоящих), иначе на таком
    экране иконка растянулась бы и замылилась.
    """
    key = (item.get("shortname"), round(ratio, 2))
    if key in _pixmap_cache:
        return _pixmap_cache[key]

    source = item.get("img")
    if source is None:
        return None

    side = max(1, int(round(ICON_SIZE * ratio)))

    # Переоткрываем файл, чтобы не держать в памяти распакованный оригинал
    path = getattr(source, "filename", None)
    if path:
        with Image.open(path) as opened:
            thumb = opened.convert("RGBA")
    else:
        thumb = source.convert("RGBA")
    thumb.thumbnail((side, side), Image.LANCZOS)

    data = thumb.tobytes("raw", "RGBA")
    image = QImage(data, thumb.width, thumb.height, thumb.width * 4, QImage.Format_RGBA8888)
    pixmap = QPixmap.fromImage(image.copy())
    # Так Qt знает, что картинка «плотнее» логических пикселей, и покажет её
    # в нужном размере, а не крупнее
    pixmap.setDevicePixelRatio(ratio)

    _pixmap_cache[key] = pixmap
    return pixmap


class FlowLayout(QLayout):
    """Раскладка, переносящая элементы на новую строку по ширине контейнера.

    Скрытые виджеты пропускаются — это позволяет фильтровать предметы
    простым setVisible(), не перестраивая раскладку целиком.
    """

    ALIGN_LEFT = "left"
    ALIGN_ROWS = "rows"    # каждая строка центрируется отдельно
    ALIGN_GRID = "grid"    # одинаковые по ширине элементы центрируются как единый блок

    def __init__(self, parent=None, margin=0, spacing=CARD_SPACING, align=ALIGN_LEFT):
        super().__init__(parent)
        self._items = []
        self._align = align
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            widget = item.widget()
            if widget is not None and widget.isHidden():
                continue
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(
            margins.left() + margins.right(), margins.top() + margins.bottom()
        )

    def _visible_items(self):
        items = []
        for item in self._items:
            widget = item.widget()
            if widget is not None and widget.isHidden():
                continue
            items.append(item)
        return items

    def _grid_offset(self, items, available):
        """Отступ слева, при котором колонки одинаковых элементов стоят по центру.

        Считается один раз на всю раскладку, поэтому неполная последняя строка
        остаётся под колонками, а не висит посреди пустого места.
        """
        if not items:
            return 0
        item_width = max(item.sizeHint().width() for item in items)
        columns = max(1, (available + self.spacing()) // (item_width + self.spacing()))
        columns = min(columns, len(items))
        block = columns * item_width + (columns - 1) * self.spacing()
        return max(0, (available - block) // 2)

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        area = rect.adjusted(
            margins.left(), margins.top(), -margins.right(), -margins.bottom()
        )
        items = self._visible_items()

        grid_offset = 0
        if self._align == self.ALIGN_GRID:
            grid_offset = self._grid_offset(items, area.width())

        def place(line, line_width, line_top, line_height):
            """Расставляет одну готовую строку."""
            if test_only:
                return
            if self._align == self.ALIGN_ROWS:
                offset = max(0, (area.width() - line_width) // 2)
            else:
                offset = grid_offset
            x = area.x() + offset
            for line_item in line:
                hint = line_item.sizeHint()
                item_y = line_top + (line_height - hint.height()) // 2
                line_item.setGeometry(QRect(QPoint(x, item_y), hint))
                x += hint.width() + self.spacing()

        y = area.y()
        line = []
        line_width = 0
        line_height = 0

        for item in items:
            hint = item.sizeHint()
            width_with_item = (
                hint.width() if not line else line_width + self.spacing() + hint.width()
            )

            if line and width_with_item > area.width():
                place(line, line_width, y, line_height)
                y += line_height + self.spacing()
                line = []
                line_width = 0
                line_height = 0
                width_with_item = hint.width()

            line.append(item)
            line_width = width_with_item
            line_height = max(line_height, hint.height())

        if line:
            place(line, line_width, y, line_height)

        return y + line_height - rect.y() + margins.bottom()


class ItemCard(QFrame):
    """Карточка одного предмета: иконка + название + отметка выбора. Кликабельна."""

    clicked = pyqtSignal(str)

    def __init__(self, label, item, parent=None):
        super().__init__(parent)
        self.label = label
        self.item = item
        self.name = item.get("Name") or item.get("shortname") or ""
        self.category = item.get("Category")
        self.search_key = self.name.lower()
        self._icon_loaded = False
        self._selected = False

        self.setObjectName("itemCard")
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(self.name)
        self.setProperty("selected", "false")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 15, 9, 12)
        layout.setSpacing(12)

        self.icon_label = QLabel(self)
        self.icon_label.setObjectName("itemIcon")
        self.icon_label.setFixedHeight(ICON_SIZE)
        self.icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.icon_label)

        name_font = QFont()
        name_font.setPointSize(12)
        metrics = QFontMetrics(name_font)

        self.name_label = QLabel(self)
        self.name_label.setObjectName("itemName")
        self.name_label.setFont(name_font)
        self.name_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.name_label.setText(
            metrics.elidedText(self.name, Qt.ElideRight, CARD_WIDTH - 21)
        )
        layout.addWidget(self.name_label)

        # Квадратик выбора поверх иконки, в правом верхнем углу карточки
        self.check_label = QLabel("", self)
        self.check_label.setObjectName("itemCheck")
        self.check_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.check_label.setFixedSize(CHECK_SIZE, CHECK_SIZE)
        self.check_label.setAlignment(Qt.AlignCenter)
        self.check_label.setProperty("selected", "false")
        self.check_label.move(CARD_WIDTH - CHECK_SIZE - 8, 8)
        self.check_label.raise_()

    @property
    def icon_loaded(self):
        return self._icon_loaded

    @property
    def is_selected(self):
        return self._selected

    def set_selected(self, selected):
        if self._selected == selected:
            return
        self._selected = selected
        self.check_label.setText("✓" if selected else "")
        for widget in (self, self.check_label):
            widget.setProperty("selected", "true" if selected else "false")
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def toggle_selected(self):
        self.set_selected(not self._selected)

    def load_icon(self):
        if self._icon_loaded:
            return
        self._icon_loaded = True
        pixmap = item_pixmap(self.item, self.devicePixelRatioF())
        if pixmap is not None:
            self.icon_label.setPixmap(pixmap)

    def reload_icon(self):
        """Перерисовывает иконку — например, после переезда на другой монитор."""
        if not self._icon_loaded:
            return
        self._icon_loaded = False
        self.load_icon()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit(self.label)
        super().mouseReleaseEvent(event)


class TabsBar(QWidget):
    """Строка вкладок-категорий, переносящаяся на следующую строку при нехватке ширины."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("tabsBar")
        self.flow = FlowLayout(self, margin=0, spacing=6, align=FlowLayout.ALIGN_ROWS)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        height = self.flow.heightForWidth(self.width())
        if self.height() != height:
            self.setFixedHeight(height)


class ItemsGrid(QWidget):
    """Контейнер карточек внутри QScrollArea.

    QScrollArea не учитывает heightForWidth содержимого, поэтому высоту
    пересчитываем вручную при каждом изменении ширины.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("itemsGrid")
        self.flow = FlowLayout(self, margin=10, align=FlowLayout.ALIGN_GRID)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

    def refresh_height(self):
        height = self.flow.heightForWidth(self.width())
        if self.minimumHeight() != height:
            self.setMinimumHeight(height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh_height()


class ItemsBrowser(QWidget):
    """Вкладки категорий + поиск + сетка предметов."""

    item_clicked = pyqtSignal(str, dict)
    selection_changed = pyqtSignal(int)
    select_requested = pyqtSignal()
    settings_requested = pyqtSignal()

    def __init__(self, categories, parent=None):
        super().__init__(parent)
        self.setObjectName("itemsBrowser")

        self._cards = []
        self._cards_by_label = {}
        self._visible_cards = []
        self._current_category = ALL_CATEGORY

        self._build_ui(categories)
        self._create_cards(categories)
        self._apply_filter()
        self._update_selected_counter()

        self._screen_ratio = None
        self._watched_window = None

    # --- построение интерфейса -------------------------------------------------

    def _build_ui(self, categories):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QFrame(self)
        toolbar.setObjectName("toolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(10, 8, 10, 8)
        toolbar_layout.setSpacing(10)

        self.category_group = QButtonGroup(self)
        self.category_group.setExclusive(True)
        self.category_group.buttonClicked.connect(self._on_category_clicked)

        self.tabs_bar = TabsBar(toolbar)
        for category in [ALL_CATEGORY] + sorted(categories, key=str.lower):
            button = QPushButton(category.upper(), self.tabs_bar)
            button.setObjectName("categoryTab")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setProperty("category", category)
            if category == ALL_CATEGORY:
                button.setChecked(True)
            self.category_group.addButton(button)
            self.tabs_bar.flow.addWidget(button)

        # Слева кнопка настроек, справа поиск. Обе одной ширины и заполнены
        # целиком — тогда вкладки посередине совпадают с центром окна,
        # а отступы по краям остаются одинаково небольшими
        self.settings_button = QPushButton("← Настройки", toolbar)
        self.settings_button.setObjectName("settingsButton")
        self.settings_button.setCursor(Qt.PointingHandCursor)
        self.settings_button.setFixedWidth(SIDE_WIDTH)
        self.settings_button.setToolTip(
            "Вернуться к настройкам игры\n(выбранные предметы сбросятся)"
        )
        self.settings_button.clicked.connect(self.settings_requested)

        toolbar_layout.addWidget(self.settings_button, 0, Qt.AlignTop)
        toolbar_layout.addWidget(self.tabs_bar, 1, Qt.AlignTop)

        self.search_edit = QLineEdit(toolbar)
        self.search_edit.setObjectName("search")
        self.search_edit.setPlaceholderText("Фильтр по названию…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(SIDE_WIDTH)
        self.search_edit.textChanged.connect(self._on_search_changed)
        toolbar_layout.addWidget(self.search_edit, 0, Qt.AlignTop)

        root.addWidget(toolbar, 0)

        action_bar = QFrame(self)
        action_bar.setObjectName("actionBar")
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(10, 8, 10, 8)
        action_layout.setSpacing(8)

        # Квадратик множественного выбора: действует на то, что сейчас на экране,
        # то есть на категорию с учётом поиска
        self.select_all_check = QCheckBox("Выделить", action_bar)
        self.select_all_check.setObjectName("selectAllCheck")
        self.select_all_check.setCursor(Qt.PointingHandCursor)
        self.select_all_check.setTristate(True)
        self.select_all_check.setToolTip(
            "Выделить все показанные предметы — категорию целиком или то,\n"
            "что нашлось по поиску"
        )
        self.select_all_check.clicked.connect(self._on_select_all_clicked)
        action_layout.addWidget(self.select_all_check)

        self.clear_all_button = QPushButton("Очистить всё", action_bar)
        self.clear_all_button.setObjectName("actionButton")
        self.clear_all_button.setCursor(Qt.PointingHandCursor)
        self.clear_all_button.setToolTip("Снять выбор со всех предметов во всех категориях")
        self.clear_all_button.clicked.connect(self.clear_selection)
        action_layout.addWidget(self.clear_all_button)

        action_layout.addStretch(1)

        self.counter_label = QLabel("", action_bar)
        self.counter_label.setObjectName("counter")
        self.counter_label.setMinimumWidth(110)
        self.counter_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        action_layout.addWidget(self.counter_label)

        self.select_button = QPushButton("Выбрать (0)", action_bar)
        self.select_button.setObjectName("selectButton")
        self.select_button.setCursor(Qt.PointingHandCursor)
        self.select_button.setToolTip("Перейти к выбранным предметам")
        self.select_button.clicked.connect(self._on_select_clicked)
        action_layout.addWidget(self.select_button)

        root.addWidget(action_bar, 0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("itemsScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.grid = ItemsGrid(self.scroll_area)
        self.scroll_area.setWidget(self.grid)
        root.addWidget(self.scroll_area, 1)

        self.empty_label = QLabel("Ничего не найдено", self)
        self.empty_label.setObjectName("emptyLabel")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.hide()
        root.addWidget(self.empty_label, 1)

        # Иконки догружаются с небольшой задержкой, чтобы не тормозить скролл
        self._icon_timer = QTimer(self)
        self._icon_timer.setSingleShot(True)
        self._icon_timer.setInterval(30)
        self._icon_timer.timeout.connect(self._load_visible_icons)
        self.scroll_area.verticalScrollBar().valueChanged.connect(
            lambda _: self._icon_timer.start()
        )

    def _create_cards(self, categories):
        seen = set()
        for category_items in categories.values():
            for label, item in self._iterate_items(category_items):
                if label in seen:
                    continue
                seen.add(label)
                card = ItemCard(label, item, self.grid)
                card.clicked.connect(self._on_card_clicked)
                self._cards.append(card)
                self._cards_by_label[label] = card

        # Общий порядок — по алфавиту, поэтому он верен и для вкладки "All"
        self._cards.sort(key=lambda card: card.search_key)
        for card in self._cards:
            self.grid.flow.addWidget(card)

    @staticmethod
    def _iterate_items(category_items):
        """Поддерживает и {метка: предмет}, и список предметов."""
        if isinstance(category_items, dict):
            return list(category_items.items())
        return [(item.get("shortname"), item) for item in category_items]

    # --- фильтрация ------------------------------------------------------------

    def _on_category_clicked(self, button: QAbstractButton):
        self._current_category = button.property("category")
        self._apply_filter()

    def _on_search_changed(self, _text):
        self._apply_filter()

    def _apply_filter(self):
        query = self.search_edit.text().strip().lower()
        category = self._current_category

        self.grid.setUpdatesEnabled(False)
        visible = []
        for card in self._cards:
            matches = (category == ALL_CATEGORY or card.category == category) and (
                not query or query in card.search_key
            )
            card.setVisible(matches)
            if matches:
                visible.append(card)
        self._visible_cards = visible

        self.grid.flow.invalidate()
        self.grid.refresh_height()
        self.grid.setUpdatesEnabled(True)

        # Набор показанных предметов сменился — квадратик пересчитываем под него
        self._sync_select_all_state()

        self.counter_label.setText(f"Найдено: {len(visible)}")
        self.empty_label.setVisible(not visible)
        self.scroll_area.setVisible(bool(visible))
        self.scroll_area.verticalScrollBar().setValue(0)

        QTimer.singleShot(0, self._load_visible_icons)

    # --- ленивая загрузка иконок ----------------------------------------------

    def _load_visible_icons(self):
        if not self._visible_cards:
            return
        viewport = self.scroll_area.viewport()
        top = self.scroll_area.verticalScrollBar().value()
        # С запасом на экран вперёд и назад, чтобы при скролле не мигали пустые карточки
        window = QRect(0, top - viewport.height(), viewport.width(), viewport.height() * 3)
        for card in self._visible_cards:
            if card.icon_loaded:
                continue
            if window.intersects(card.geometry()):
                card.load_icon()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.grid.refresh_height()
        self._icon_timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        # Окно могли перетащить на монитор с другим масштабом — тогда иконки
        # нужно перерисовать под новую плотность пикселей
        handle = self.window().windowHandle()
        if handle is not None and handle is not self._watched_window:
            self._watched_window = handle
            handle.screenChanged.connect(self._on_screen_changed)
        self._screen_ratio = self.devicePixelRatioF()

    def _on_screen_changed(self, _screen):
        ratio = self.devicePixelRatioF()
        if ratio == self._screen_ratio:
            return   # масштаб тот же, перерисовывать нечего
        self._screen_ratio = ratio
        for card in self._cards:
            card.reload_icon()

    # --- выбор предметов -------------------------------------------------------

    def _on_card_clicked(self, label):
        card = self._cards_by_label.get(label)
        if card is None:
            return
        card.toggle_selected()
        self._update_selected_counter()
        self.item_clicked.emit(label, card.item)

    def _on_select_clicked(self):
        """Пускает к распознаванию только если есть что искать."""
        if not any(card.is_selected for card in self._cards):
            message = QMessageBox(self)
            message.setObjectName("appMessage")
            message.setIcon(QMessageBox.Warning)
            message.setWindowTitle("Предметы не выбраны")
            message.setText("Не выбрано ни одного предмета.")
            message.setInformativeText(
                "Отметьте хотя бы один предмет, который нужно искать: "
                "нажмите на карточку, чтобы поставить галочку."
            )
            message.setStandardButtons(QMessageBox.Ok)
            message.button(QMessageBox.Ok).setText("Понятно")
            message.exec_()
            return

        self.select_requested.emit()

    def _on_select_all_clicked(self, _checked):
        """Квадратик множественного выбора.

        Qt на клике сам крутит три состояния по кругу, поэтому решение
        принимаем не по нему, а по тому, что реально выделено: показано всё —
        снимаем, иначе (ничего или часть) — выделяем всё.
        """
        if self._visible_cards and all(card.is_selected for card in self._visible_cards):
            self.clear_shown()
        else:
            self.select_shown()

    def _sync_select_all_state(self):
        """Приводит квадратик в соответствие с тем, что выделено на экране."""
        selected = sum(1 for card in self._visible_cards if card.is_selected)
        if not self._visible_cards:
            state = Qt.Unchecked
        elif selected == len(self._visible_cards):
            state = Qt.Checked
        elif selected == 0:
            state = Qt.Unchecked
        else:
            state = Qt.PartiallyChecked

        # setCheckState не поднимает clicked, так что рекурсии здесь нет
        self.select_all_check.setCheckState(state)
        self.select_all_check.setEnabled(bool(self._visible_cards))

    def select_shown(self):
        """Выбирает все предметы, показанные сейчас (категория + поиск)."""
        self._set_selected(self._visible_cards, True)

    def clear_shown(self):
        """Снимает выбор с предметов, показанных сейчас (категория + поиск)."""
        self._set_selected(self._visible_cards, False)

    def clear_selection(self):
        """Снимает выбор со всех предметов во всех категориях."""
        self._set_selected(self._cards, False)

    def _set_selected(self, cards, selected):
        self.grid.setUpdatesEnabled(False)
        for card in cards:
            card.set_selected(selected)
        self.grid.setUpdatesEnabled(True)
        self._update_selected_counter()

    def _update_selected_counter(self):
        count = sum(1 for card in self._cards if card.is_selected)
        self.select_button.setText(f"Выбрать ({count})")
        self._sync_select_all_state()
        self.selection_changed.emit(count)

    def selected_labels(self):
        """Метки выбранных предметов."""
        return [card.label for card in self._cards if card.is_selected]

    def selected_items(self):
        """Выбранные предметы: {метка: предмет}."""
        return {card.label: card.item for card in self._cards if card.is_selected}
