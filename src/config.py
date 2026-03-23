# src/config.py
import json
import os
from typing import Dict, Any

DEFAULTS: Dict[str, Any] = {
    "config_version": 1,
    "bt_active_mac": "",
    "bt_max_paired_devices": 5,
    "dect_dongle_vid_pid": "auto",
    "operation_mode": "dynamic",
    "hold_time_ms": 3000,
    "profiles": {
        "xlr5_bt":   {"input_db": 20, "output_db": 0},
        "xlr5_dect": {"input_db": 20, "output_db": 0},
        "wire4_bt":  {"input_db": 0,  "output_db": 0},
        "wire4_dect": {"input_db": 0,  "output_db": 0},
    },
    "sidetone": {
        "bt_enabled": False, "bt_level_db": -12,
        "dect_enabled": False, "dect_level_db": -12,
    },
    "ble_ptt_enabled": False,
    "ble_ptt_mac": "",
    "hotspot_ssid": "MiniHop-0000",
    "hotspot_password": "minihop1",
    "hotspot_pairing_window_s": 300,
}


class Config:
    def __init__(self, path: str = "/home/pi/minihop/config.json"):
        self._path = path
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if os.path.exists(self._path) and os.path.getsize(self._path) > 0:
            with open(self._path) as f:
                on_disk = json.load(f)
            # Migrate: fill in any keys missing from older configs
            self._data = {**DEFAULTS, **on_disk}
            # Deep merge profiles and sidetone
            self._data["profiles"] = {**DEFAULTS["profiles"], **on_disk.get("profiles", {})}
            self._data["sidetone"] = {**DEFAULTS["sidetone"], **on_disk.get("sidetone", {})}
        else:
            self._data = dict(DEFAULTS)
            self._data["profiles"] = {k: dict(v) for k, v in DEFAULTS["profiles"].items()}
            self._data["sidetone"] = dict(DEFAULTS["sidetone"])
            self.save()

    def save(self):
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._data, f, indent=2)

    # --- Property accessors ---

    @property
    def operation_mode(self) -> str:
        return self._data["operation_mode"]

    @operation_mode.setter
    def operation_mode(self, value: str):
        assert value in ("dynamic", "latch", "permanent")
        self._data["operation_mode"] = value

    @property
    def hold_time_ms(self) -> int:
        return self._data["hold_time_ms"]

    @hold_time_ms.setter
    def hold_time_ms(self, value: int):
        self._data["hold_time_ms"] = int(value)

    @property
    def bt_active_mac(self) -> str:
        return self._data["bt_active_mac"]

    @bt_active_mac.setter
    def bt_active_mac(self, value: str):
        self._data["bt_active_mac"] = value

    @property
    def bt_max_paired_devices(self) -> int:
        return self._data["bt_max_paired_devices"]

    @property
    def dect_dongle_vid_pid(self) -> str:
        return self._data["dect_dongle_vid_pid"]

    @property
    def sidetone(self) -> dict:
        return self._data["sidetone"]

    @property
    def ble_ptt_enabled(self) -> bool:
        return self._data["ble_ptt_enabled"]

    @property
    def ble_ptt_mac(self) -> str:
        return self._data.get("ble_ptt_mac", "")

    @ble_ptt_mac.setter
    def ble_ptt_mac(self, value: str):
        self._data["ble_ptt_mac"] = value

    @property
    def hotspot_ssid(self) -> str:
        return self._data["hotspot_ssid"]

    @property
    def hotspot_password(self) -> str:
        return self._data["hotspot_password"]

    @property
    def hotspot_pairing_window_s(self) -> int:
        return self._data["hotspot_pairing_window_s"]

    def get_profile(self, key: str) -> dict:
        return dict(self._data["profiles"][key])

    def set_profile(self, key: str, input_db: int = None, output_db: int = None):
        if input_db is not None:
            self._data["profiles"][key]["input_db"] = input_db
        if output_db is not None:
            self._data["profiles"][key]["output_db"] = output_db
