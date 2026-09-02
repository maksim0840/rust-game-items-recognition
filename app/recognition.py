import json
import os

import numpy as np
import onnxruntime as ort
from PIL import Image
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication

from monitors import QtMonitors
from screen_capture import capture_monitor

APP_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_INFO_DIR = os.path.join(APP_DIR, "model")

# centroids.pt — это архив torch, numpy читает его как NpzFile: нужен .npy
MODEL_CENTROIDS = "centroids.npy"
MODEL_ONNX = "item_recognizer.onnx"
MODEL_PREPROCESS = "preprocess.json"

RUST_CHEST_N_COLS = 6
RUST_CHEST_N_ROWS = 8


class InventoryGrid:
    # Посчитанные параметры для определения коэффициентов сетки
    GRID_MODEL_ARGS = {
        'x0':      (0.15538758, 0.49977814),    # * width
        'delta_w': (0.04845760, -0.00002766),   # * width
        'cell_w':  (0.04531963, -0.00045448),   # * width
        'y0':      (-0.83747928, 0.99939329),   # * height
        'delta_h': (0.08609323, 0.00002244),    # * height
        'cell_h':  (0.08054795, -0.00079300),   # * height
    }

    # Предсказывает коэффициенты сетки по известному разрешению экрана и scale
    @staticmethod
    def _predict_grid_params(width, height, scale):
        def v(param, dim):
            a, k = InventoryGrid.GRID_MODEL_ARGS[param]
            return dim * (a * scale + k)
        return {
            'x0':      v('x0', width),
            'delta_w': v('delta_w', width),
            'cell_w':  v('cell_w', width),
            'y0':      v('y0', height),
            'delta_h': v('delta_h', height),
            'cell_h':  v('cell_h', height),
        }

    # Возращаем координаты всех ячеек сундука
    # Каждая ячейка: (tl_x, tl_y, br_x, br_y) tl — верхний левый угол, br — нижний правый.
    @staticmethod
    def all_slot_boxes(width, height, scale, n_cols, n_rows):
        p = InventoryGrid._predict_grid_params(width, height, scale)
        x0, dw, cw = p['x0'], p['delta_w'], p['cell_w']
        y0, dh, ch = p['y0'], p['delta_h'], p['cell_h']
        boxes = []
        for row in range(n_rows):
            for col in range(n_cols):
                boxes.append((
                    round(x0 + col*dw),        # x1
                    round(y0 + row*dh),        # y1
                    round(x0 + col*dw + cw),   # x2
                    round(y0 + row*dh + ch),   # y2
                ))
        return boxes

    # Нарезает изображение сундука на ячейки по модели сетки
    @staticmethod
    def extract_cells(img: Image.Image, width, height, scale, n_cols, n_rows, inset=3):
        """
        Возвращает список из n_cols*n_rows словарей:
        {'row', 'col', 'box' (рамка без отступа), 'image' (кроп PIL.Image)}
        """
        W, H = img.size
        if ((W, H) != (width, height)):
            raise ValueError(
                "Размер изображения %dx%d не совпадает с настройками %dx%d. "
                "Сетка ячеек считается от разрешения экрана, поэтому по чужому "
                "размеру координаты ячеек оказались бы неверными."
                % (W, H, width, height)
            )

        # 2) координаты всех ячеек по модели
        boxes = InventoryGrid.all_slot_boxes(W, H, scale, n_cols, n_rows)

        # 3) режем
        cells = []
        for idx, (x1, y1, x2, y2) in enumerate(boxes):
            row, col = divmod(idx, n_cols)
            cx1 = max(0, min(W, x1 + inset)); cy1 = max(0, min(H, y1 + inset))
            cx2 = max(0, min(W, x2 - inset)); cy2 = max(0, min(H, y2 - inset))
            crop = img.crop((cx1, cy1, cx2, cy2))
            cells.append({'row': row, 'col': col, 'box': (x1, y1, x2, y2), 'image': crop})
        return cells


class ItemRecognitionModel:
    def __init__(self, cuda_provider=False):
        provider = 'CUDAExecutionProvider' if cuda_provider else 'CPUExecutionProvider'
        if provider not in ort.get_available_providers():
            provider = 'CPUExecutionProvider'  # сборка onnxruntime без GPU просто не знает про CUDA 
        self.provider = provider

        self.model = ort.InferenceSession(
            os.path.join(MODEL_INFO_DIR, MODEL_ONNX), providers=[provider]
        )  # модель
        self.input_name = self.model.get_inputs()[0].name

        self.centroids = np.load(
            os.path.join(MODEL_INFO_DIR, MODEL_CENTROIDS)
        )  # центроиды классов

        with open(os.path.join(MODEL_INFO_DIR, MODEL_PREPROCESS), encoding='utf-8') as file:
            preprocess_cfg = json.load(file)  # параметры обработки
        self.INPUT_SIZE = tuple(preprocess_cfg["input_size"])      # (224, 224)
        self.THRESHOLD = preprocess_cfg["threshold"]               # 0.73

    # Подготавливаем изображение перед предсказанием модели
    def _preprocess_img(self, image: Image.Image):
        """
        PIL.Image -> numpy [1, 3, 224, 224], float32 в диапазоне [0,1].
        Воспроизводит то, что делал ToTensor() при обучении.
        """
        img = image.convert('RGB').resize(self.INPUT_SIZE, Image.BILINEAR)

        arr = np.asarray(img, dtype=np.float32) / 255.0   # [H, W, C] в [0,1]
        arr = arr.transpose(2, 0, 1)                      # -> [C, H, W]
        return arr[np.newaxis, ...]                       # -> [1, C, H, W]

    # Предсказываем класс предмета
    def predict(self, image: Image.Image):
        """
        Возвращает (название, уверенность) или (None, уверенность), если модель не уверена.
        """
        x = self._preprocess_img(image)
        emb = self.model.run(None, {self.input_name: x})[0]   # [1, 256], уже нормализован моделью

        sims = (emb @ self.centroids.T)[0]                     # близость к каждому центроиду
        idx = int(sims.argmax())
        conf = float(sims[idx])

        if conf < self.THRESHOLD:
            return None, conf                             # "не уверен"
        return str(idx), conf

    # Более быстрое предсказание классов нескольких предметов через батч
    def predict_batch(self, images):
        """Прогоняет список картинок разом. Возвращает список (название, уверенность)."""
        if not images:
            return []

        batch = np.concatenate(
            [self._preprocess_img(im) for im in images], axis=0
        )                                                     # [N, 3, 224, 224]
        embs = self.model.run(None, {self.input_name: batch})[0]   # [N, 256]

        sims = embs @ self.centroids.T                                           # [N, n_classes]
        idxs = sims.argmax(axis=1)
        confs = sims.max(axis=1)

        return [(str(int(idx)) if conf >= self.THRESHOLD else None, float(conf))
                for idx, conf in zip(idxs, confs)]


class InventoryScanner:
    def __init__(self, grid: InventoryGrid, recognition: ItemRecognitionModel,
                 width, height, scale, n_cols, n_rows, screen_name=None):
        self.grid = grid
        self.recognition = recognition
        self.width = width
        self.height = height
        self.scale = scale
        self.n_cols = n_cols
        self.n_rows = n_rows
        self.screen_name = screen_name   # имя монитора из окна настроек

    @classmethod
    def from_settings(cls, grid, recognition, settings,
                      n_cols=RUST_CHEST_N_COLS, n_rows=RUST_CHEST_N_ROWS):
        """Собирает предсказатель прямо из словаря SettingsDialog.settings()."""
        return cls(
            grid,
            recognition,
            settings["width"],
            settings["height"],
            settings["ui_scale"],
            n_cols,
            n_rows,
            screen_name=settings.get("screen_name"),
        )

    def _resolve_screen(self, qt_monitor=None):
        """Находит QScreen: по готовому объекту, по имени или по настройкам."""
        if QApplication.instance() is None:
            raise RuntimeError(
                "Снимок экрана делается средствами Qt, поэтому нужен запущенный "
                "QApplication — создайте его до вызова make_screenshot()."
            )

        if qt_monitor is not None and not isinstance(qt_monitor, str):
            return qt_monitor   # уже готовый QScreen

        name = qt_monitor if isinstance(qt_monitor, str) else self.screen_name
        if name is None:
            return QApplication.instance().primaryScreen()

        screen = QtMonitors.screen_for(name)
        if screen is None:
            raise RuntimeError(
                "Монитор %r не найден среди подключённых — возможно, его отключили "
                "после того, как настройки были подтверждены." % (name,)
            )
        return screen

    def make_screenshot(self, qt_monitor=None):
        """Снимает выбранный монитор целиком и возвращает PIL.Image.

        qt_monitor: QScreen, имя монитора или None — тогда берётся монитор,
        выбранный в окне настроек.
        """
        screen = self._resolve_screen(qt_monitor)

        # Снимаем средствами Windows, а не Qt: метрики Qt зависят от режима
        # DPI-осведомлённости и для неосновных мониторов дают растянутый кадр
        screenshot = capture_monitor(screen.name())

        if screenshot.size != (self.width, self.height):
            raise ValueError(
                "Снимок монитора %r получился %dx%d, а в настройках указано %dx%d — "
                "похоже, разрешение экрана изменилось. Вернитесь к настройкам."
                % (screen.name(), screenshot.width, screenshot.height,
                   self.width, self.height)
            )
        return screenshot

    def find_classes_on_screenshot(self, screenshot: Image.Image, classes: set):
        detected_cells = self.grid.extract_cells(
            screenshot, self.width, self.height, self.scale, self.n_cols, self.n_rows
        )
        item_imgs = [cell['image'] for cell in detected_cells]

        preds = self.recognition.predict_batch(item_imgs)
        if (len(preds) != len(detected_cells)):
            raise RuntimeError(
                "Модель вернула %d предсказаний на %d ячеек — сопоставить их "
                "с координатами ячеек невозможно." % (len(preds), len(detected_cells))
            )

        matched_coords = []
        undefined_coords = []
        not_matched_coords = []

        for i in range(len(detected_cells)):
            label, conf = preds[i]
            if (label is None):
                undefined_coords.append(detected_cells[i]["box"])
            elif (label in classes):
                matched_coords.append(detected_cells[i]["box"])
            else: # (label not in classes)
                not_matched_coords.append(detected_cells[i]["box"])

        return matched_coords, undefined_coords, not_matched_coords


def qpixmap_to_pil(pixmap):
    """QPixmap -> PIL.Image через сырые пиксели RGBA."""
    image = pixmap.toImage().convertToFormat(QImage.Format_RGBA8888)
    buffer = image.constBits().asstring(image.height() * image.bytesPerLine())
    return Image.frombytes(
        "RGBA", (image.width(), image.height()), buffer,
        "raw", "RGBA", image.bytesPerLine(),
    ).convert("RGB")


# if __name__ == "__main__":
#     import sys

#     app = QApplication(sys.argv)   # нужен для снимка экрана

#     grid = InventoryGrid()
#     recognition = ItemRecognitionModel()

#     scanner = InventoryScanner(
#         grid, recognition, 2560, 1440, 1.00,
#         RUST_CHEST_N_COLS, RUST_CHEST_N_ROWS,
#         screen_name=None,   # None — основной монитор
#     )

#     screenshot = scanner.make_screenshot()
#     matched_coords, undefined_coords, not_matched_coords = (
#         scanner.find_classes_on_screenshot(screenshot, {"1", "5", "0"})
#     )

#     print(f"=== matched: {len(matched_coords)} ===")
#     print(matched_coords)
#     print()

#     print(f"=== undefined: {len(undefined_coords)} ===")
#     print(undefined_coords)
#     print()

#     print(f"=== not_matched: {len(not_matched_coords)} ===")
#     print(not_matched_coords)
#     print()
