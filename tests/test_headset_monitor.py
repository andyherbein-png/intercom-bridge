# tests/test_headset_monitor.py
import pytest
from unittest.mock import MagicMock
from src.headset_monitor import HeadsetMonitor
from src.state_machine import Event, HeadsetType


@pytest.fixture
def monitor():
    mock_config = MagicMock()
    mock_config.dect_dongle_vid_pid = "auto"
    sm = MagicMock()
    return HeadsetMonitor(mock_config, sm), sm


def test_dect_add_event_fires_connected(monitor):
    mon, sm = monitor
    fake_device = MagicMock()
    fake_device.action = "add"
    fake_device.subsystem = "usb"
    fake_device.get.return_value = "Jabra"  # manufacturer
    mon._on_usb_event(fake_device)
    sm.set_headset_type.assert_called_with(HeadsetType.DECT)
    sm.handle.assert_called_with(Event.HEADSET_CONNECTED)


def test_dect_remove_event_fires_disconnected(monitor):
    mon, sm = monitor
    fake_device = MagicMock()
    fake_device.action = "remove"
    fake_device.subsystem = "usb"
    fake_device.get.return_value = "Jabra"
    mon._on_usb_event(fake_device)
    sm.handle.assert_called_with(Event.HEADSET_DISCONNECTED)


def test_non_dect_usb_ignored(monitor):
    mon, sm = monitor
    fake_device = MagicMock()
    fake_device.action = "add"
    fake_device.subsystem = "usb"
    fake_device.get.return_value = "SomethingElse"
    mon._on_usb_event(fake_device)
    sm.handle.assert_not_called()
