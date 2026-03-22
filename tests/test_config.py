# tests/test_config.py
import json
import pytest
from src.config import Config


@pytest.fixture
def tmp_config(tmp_path):
    return tmp_path / "config.json"


def test_creates_defaults_when_file_missing(tmp_config):
    cfg = Config(str(tmp_config))
    assert cfg.operation_mode == "dynamic"
    assert cfg.hold_time_ms == 3000
    assert cfg.bt_max_paired_devices == 5
    assert tmp_config.exists()


def test_reads_existing_file(tmp_config):
    data = {
        "config_version": 1, "operation_mode": "latch", "hold_time_ms": 2000,
        "bt_active_mac": "AA:BB:CC:DD:EE:FF", "bt_max_paired_devices": 5,
        "dect_dongle_vid_pid": "auto", "profiles": {
            "xlr5_bt": {"input_db": 20, "output_db": 0},
            "xlr5_dect": {"input_db": 20, "output_db": 0},
            "wire4_bt": {"input_db": 0, "output_db": 0},
            "wire4_dect": {"input_db": 0, "output_db": 0}},
        "sidetone": {"bt_enabled": False, "bt_level_db": -12,
                     "dect_enabled": False, "dect_level_db": -12},
        "ble_ptt_enabled": False, "ble_ptt_mac": "",
        "hotspot_ssid": "TestSSID", "hotspot_password": "testpass",
        "hotspot_pairing_window_s": 300,
    }
    tmp_config.write_text(json.dumps(data))
    cfg = Config(str(tmp_config))
    assert cfg.operation_mode == "latch"
    assert cfg.hold_time_ms == 2000
    assert cfg.bt_active_mac == "AA:BB:CC:DD:EE:FF"


def test_save_and_reload(tmp_config):
    cfg = Config(str(tmp_config))
    cfg.operation_mode = "permanent"
    cfg.save()
    cfg2 = Config(str(tmp_config))
    assert cfg2.operation_mode == "permanent"


def test_get_profile(tmp_config):
    cfg = Config(str(tmp_config))
    p = cfg.get_profile("xlr5_bt")
    assert "input_db" in p and "output_db" in p


def test_set_profile(tmp_config):
    cfg = Config(str(tmp_config))
    cfg.set_profile("xlr5_bt", input_db=15, output_db=-3)
    cfg.save()
    cfg2 = Config(str(tmp_config))
    assert cfg2.get_profile("xlr5_bt")["input_db"] == 15


def test_migration_adds_missing_keys(tmp_config):
    # Simulate old config missing new keys
    old = {"config_version": 1, "operation_mode": "dynamic"}
    tmp_config.write_text(json.dumps(old))
    cfg = Config(str(tmp_config))
    # Should fill defaults for missing keys without crashing
    assert cfg.hold_time_ms == 3000
    assert cfg.bt_max_paired_devices == 5
