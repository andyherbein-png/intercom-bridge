# src/headset_monitor.py
import logging
import threading
from src.state_machine import Event, HeadsetType

logger = logging.getLogger(__name__)

# Known DECT dongle manufacturers/product strings
DECT_IDENTIFIERS = {"jabra", "epos", "yealink", "dect", "dhsg"}


class HeadsetMonitor:
    def __init__(self, config, state_machine):
        self._cfg = config
        self._sm = state_machine
        self._monitor_thread = None

    def start(self):
        t = threading.Thread(target=self._run_monitor, daemon=True)
        t.start()
        self._monitor_thread = t

    def _run_monitor(self):
        try:
            import pyudev
            context = pyudev.Context()
            monitor = pyudev.Monitor.from_netlink(context)
            monitor.filter_by(subsystem="usb")
            for device in iter(monitor.poll, None):
                self._on_usb_event(device)
        except ImportError:
            logger.warning("pyudev not available — DECT USB monitoring disabled")
        except Exception as e:
            logger.error("HeadsetMonitor crashed: %s", e)

    def _on_usb_event(self, device):
        if device.subsystem != "usb":
            return
        manufacturer = (device.get("ID_VENDOR", "") or "").lower()
        product = (device.get("ID_MODEL", "") or "").lower()
        combined = manufacturer + " " + product

        if not any(k in combined for k in DECT_IDENTIFIERS):
            return

        if device.action == "add":
            logger.info("DECT dongle connected: %s", combined)
            self._sm.set_headset_type(HeadsetType.DECT)
            self._sm.handle(Event.HEADSET_CONNECTED)
        elif device.action == "remove":
            logger.info("DECT dongle removed: %s", combined)
            self._sm.handle(Event.HEADSET_DISCONNECTED)
