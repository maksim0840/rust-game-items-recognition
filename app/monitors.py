"""Всё, что известно о подключённых мониторах.

Два слоя:

* MonitorNames — настоящие названия моделей из EDID. Windows-только, Qt не
  требуется, работает даже без запущенного QApplication.
* QtMonitors — перечисление мониторов средствами Qt (разрешение, частота,
  основной монитор), дополненное названиями из первого слоя. Это то, чем
  пользуется остальная программа.

Подписи для интерфейса здесь не собираются: модуль отдаёт данные, а как их
назвать по-русски — дело того окна, которое их показывает.
"""

import re
import sys

from PyQt5.QtWidgets import QApplication

from screen_capture import display_mode

IS_WINDOWS = sys.platform == "win32"

EDD_GET_DEVICE_INTERFACE_NAME = 0x00000001
DISPLAY_DEVICE_ATTACHED_TO_DESKTOP = 0x1

EDID_HEADER = b"\x00\xff\xff\xff\xff\xff\xff\x00"
EDID_DESCRIPTOR_OFFSETS = (54, 72, 90, 108)
EDID_MONITOR_NAME_TAG = 0xFC


class MonitorNames:
    """Названия мониторов по имени видеовыхода.

    Ключ — то же, что возвращает QScreen.name(), например "\\\\.\\DISPLAY1".
    Значение — {"model": "Odyssey G52A", "vendor": "SAM"}, где vendor —
    трёхбуквенный PnP-код производителя.

    Мониторы, у которых название прочитать не удалось, в словарь не попадают;
    если не удалось ничего — словарь пустой, и вызывающий код обойдётся
    номерами мониторов.
    """

    def __init__(self):
        self._names = None

    def all(self):
        """Все известные названия. Читается один раз и запоминается."""
        if self._names is None:
            self._names = self._load()
        return self._names

    def get(self, device_name):
        """Название одного монитора или пустой словарь, если оно неизвестно."""
        return self.all().get(device_name, {})

    def refresh(self):
        """Забыть прочитанное — например, когда монитор подключили заново."""
        self._names = None

    @classmethod
    def _load(cls):
        if not IS_WINDOWS:
            return {}
        try:
            return cls._load_from_registry()
        except Exception:
            # Названия — украшение, а не необходимость: любая неожиданность
            # здесь не должна ломать окно настроек
            return {}

    @staticmethod
    def _load_from_registry():
        """Достаёт EDID каждого монитора из реестра Windows."""
        import ctypes
        import winreg
        from ctypes import wintypes

        class DISPLAY_DEVICE(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("DeviceName", wintypes.WCHAR * 32),
                ("DeviceString", wintypes.WCHAR * 128),
                ("StateFlags", wintypes.DWORD),
                ("DeviceID", wintypes.WCHAR * 128),
                ("DeviceKey", wintypes.WCHAR * 128),
            ]

        user32 = ctypes.windll.user32

        def enumerate_devices(device, flags=0):
            devices = []
            index = 0
            while True:
                info = DISPLAY_DEVICE()
                info.cb = ctypes.sizeof(DISPLAY_DEVICE)
                if not user32.EnumDisplayDevicesW(device, index, ctypes.byref(info), flags):
                    break
                devices.append(info)
                index += 1
            return devices

        names = {}
        for adapter in enumerate_devices(None):
            if not adapter.StateFlags & DISPLAY_DEVICE_ATTACHED_TO_DESKTOP:
                continue

            for monitor in enumerate_devices(
                adapter.DeviceName, EDD_GET_DEVICE_INTERFACE_NAME
            ):
                # DeviceID выглядит так:
                # \\?\DISPLAY#SAM7181#5&32bf01ae&0&UID4353#{e6f07b5f-...}
                parts = monitor.DeviceID.split("#")
                if len(parts) < 3:
                    continue
                pnp_id, instance = parts[1], parts[2]

                key_path = (
                    r"SYSTEM\CurrentControlSet\Enum\DISPLAY\%s\%s\Device Parameters"
                    % (pnp_id, instance)
                )
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                        edid, _ = winreg.QueryValueEx(key, "EDID")
                except OSError:
                    continue

                model, vendor = MonitorNames._parse_edid(bytes(edid))
                if model:
                    names[adapter.DeviceName] = {"model": model, "vendor": vendor}
                break  # у адаптера в этом перечислении один монитор

        return names

    @staticmethod
    def _parse_edid(edid):
        """Достаёт из EDID название модели и код производителя."""
        if len(edid) < 128 or edid[:8] != EDID_HEADER:
            return None, None

        # Код производителя — три буквы по пять бит в байтах 8-9
        packed = (edid[8] << 8) | edid[9]
        vendor = "".join(
            chr(((packed >> shift) & 0x1F) + ord("A") - 1) for shift in (10, 5, 0)
        )

        model = None
        for offset in EDID_DESCRIPTOR_OFFSETS:
            block = edid[offset:offset + 18]
            if len(block) < 18 or block[0:3] != b"\x00\x00\x00":
                continue
            if block[3] == EDID_MONITOR_NAME_TAG:
                text = block[5:18].split(b"\x0a")[0].decode("cp437", "ignore").strip()
                if text:
                    model = text

        return model, vendor


class QtMonitors:
    """Подключённые мониторы глазами Qt, дополненные названиями из EDID.

    Требует запущенного QApplication. Каждый монитор описывается словарём:

        {
            "name":    "\\\\.\\DISPLAY1",   # то же, что QScreen.name()
            "model":   "Odyssey G52A",  # None, если название неизвестно
            "vendor":  "SAM",           # None, если название неизвестно
            "number":  "1",             # номер как в настройках системы
            "width":   2560,            # физические пиксели
            "height":  1440,
            "refresh": 165,             # Гц, 0 если неизвестно
            "primary": True,
        }
    """

    def __init__(self, names=None):
        self._names = names if names is not None else MonitorNames()

    def refresh(self):
        """Перечитать названия — мониторы могли переподключить."""
        self._names.refresh()

    def all(self):
        """Все подключённые мониторы, по порядку их номеров в системе."""
        app = QApplication.instance()
        if app is None:
            return []

        primary = app.primaryScreen()
        monitors = []

        for index, screen in enumerate(app.screens()):
            width, height = self.resolution(screen)
            name = screen.name()
            real_name = self._names.get(name)

            monitors.append(
                {
                    "name": name,
                    "model": real_name.get("model"),
                    "vendor": real_name.get("vendor"),
                    "number": self._number(name, index),
                    "width": width,
                    "height": height,
                    "refresh": round(screen.refreshRate()) if screen.refreshRate() else 0,
                    "primary": screen is primary,
                }
            )

        # Qt отдаёт мониторы в произвольном порядке — сортируем по номеру,
        # чтобы нумерация совпадала с настройками системы
        monitors.sort(
            key=lambda item: (
                not item["number"].isdigit(),
                int(item["number"]) if item["number"].isdigit() else 0,
                item["name"],
            )
        )
        return monitors

    def find(self, device_name):
        """Описание одного монитора по его имени или None."""
        for monitor in self.all():
            if monitor["name"] == device_name:
                return monitor
        return None

    @staticmethod
    def screen_for(device_name):
        """QScreen по имени монитора — он понадобится, например, для снимка экрана.

        Объект ищется заново при каждом вызове: при отключении монитора
        Qt удаляет QScreen, и сохранённая ссылка стала бы висячей.
        """
        app = QApplication.instance()
        if app is None:
            return None
        for screen in app.screens():
            if screen.name() == device_name:
                return screen
        return None

    @staticmethod
    def resolution(screen):
        """Настоящее разрешение монитора в пикселях.

        Спрашиваем у Windows напрямую: метрики Qt зависят от того, как
        объявлена DPI-осведомлённость процесса, и для неосновных мониторов
        оказываются виртуализированными.
        """
        mode = display_mode(screen.name())
        if mode is not None:
            return mode[2], mode[3]

        # Запасной путь (не Windows или Win32 не ответил)
        ratio = screen.devicePixelRatio()
        size = screen.size()
        return round(size.width() * ratio), round(size.height() * ratio)

    @staticmethod
    def _number(device_name, index):
        """Номер монитора: на Windows имя выглядит как "\\\\.\\DISPLAY2"."""
        match = re.search(r"(\d+)\s*$", device_name or "")
        return match.group(1) if match else str(index + 1)
