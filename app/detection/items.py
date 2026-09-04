import json
from PIL import Image

from paths import ITEMS_IMAGES_DIR, MODEL_DIR

ITEMS_IMGS_DIR = ITEMS_IMAGES_DIR
ITEM_IMG_EXT = "png"

MODEL_INFO_DIR = MODEL_DIR
MODEL_CLASS_MAPPING = "class_mapping.json"

ALL_CATEGORY = "All"

class RustItemsLoader:
    def __init__(self):
        self.items_data = {}

    def load_items_data(self):
        # Получаем текстовую информацию о предмете по его метке
        with open(f'{MODEL_INFO_DIR}/{MODEL_CLASS_MAPPING}', 'r', encoding='utf-8') as file:
            self.items_data = json.load(file)

        # Загружаем иконку предмета
        for label, data in self.items_data.items():
            if (data["shortname"] is None): # пустая ячейка
                self.items_data[label]["img"] = None
                continue
            item_img = Image.open(f"{ITEMS_IMGS_DIR}/{data['shortname']}.{ITEM_IMG_EXT}")
            self.items_data[label]["img"] = item_img

    def get_items_data(self):
        return self.items_data


def distribute_items_into_categories(items_data):
    """Группирует предметы по категориям: {категория: {метка: предмет}}.

    Категории отсортированы по алфавиту, предметы внутри категории — по названию.
    Пустые ячейки (без shortname) пропускаются.
    """
    categories = {}
    for label, data in items_data.items():
        if data.get("shortname") is None or data.get("Category") is None:
            continue
        categories.setdefault(data["Category"], {})[label] = data

    result = {}
    for category in sorted(categories, key=str.lower):
        items = categories[category]
        result[category] = dict(
            sorted(items.items(), key=lambda pair: (pair[1]["Name"] or "").lower())
        )
    return result


rust_items_loader = RustItemsLoader()
rust_items_loader.load_items_data()

items = rust_items_loader.get_items_data()
