import json
from PIL import Image

ITEMS_IMGS_DIR = "/home/user/Documents/rust-items-detection/app/items"
ITEM_IMG_EXT = "png"

MODEL_INFO_DIR = "/home/user/Documents/rust-items-detection/app/model"
MODEL_CLASS_MAPPING = "class_mapping.json"

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
            item_img = Image.open(f"{ITEMS_IMGS_DIR}/{data["shortname"]}.{ITEM_IMG_EXT}")
            self.items_data[label]["img"] = item_img
    
    def get_items_data(self):
        return self.items_data

rust_items_loader = RustItemsLoader()
rust_items_loader.load_items_data()

items = rust_items_loader.get_items_data()

print(items)