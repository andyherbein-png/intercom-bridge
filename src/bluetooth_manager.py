# src/bluetooth_manager.py
import logging
import threading
from typing import Callable, List, Optional
from src.state_machine import Event

logger = logging.getLogger(__name__)

# BlueZ D-Bus constants
BLUEZ_SERVICE = "org.bluez"
DEVICE_IFACE = "org.bluez.Device1"
MEDIA_TRANSPORT_IFACE = "org.bluez.MediaTransport1"
HFP_UUID = "0000111e-0000-1000-8000-00805f9b34fb"
A2DP_UUID = "0000110b-0000-1000-8000-00805f9b34fb"

try:
    from dasbus.connection import SystemMessageBus as SystemBus
except ImportError:
    # Allow import without dasbus installed (unit tests mock it)
    SystemBus = None


class BluetoothManager:
    def __init__(self):
        self._callbacks: List[Callable] = []
        self._active_mac: Optional[str] = None
        self._bus = None
        self._device_proxy = None
        try:
            if SystemBus:
                self._bus = SystemBus()
        except Exception as e:
            logger.warning(f"BlueZ D-Bus unavailable: {e}")

    def on_event(self, cb: Callable):
        self._callbacks.append(cb)

    def _fire(self, event: Event):
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def set_active_device(self, mac: str):
        self._active_mac = mac
        if self._bus and mac:
            path = "/org/bluez/hci0/dev_" + mac.replace(":", "_")
            try:
                self._device_proxy = self._bus.get_proxy(BLUEZ_SERVICE, path)
            except Exception as e:
                logger.warning(f"Could not get device proxy for {mac}: {e}")

    def switch_to_hfp(self):
        """Request A2DP→HFP profile switch. Fires HFP_ACTIVE when BlueZ confirms."""
        if not self._active_mac:
            logger.warning("switch_to_hfp called with no active device")
            return
        try:
            self._set_profile(HFP_UUID)
            # HFP_ACTIVE fires via D-Bus property change signal (registered in start())
        except Exception as e:
            logger.error(f"switch_to_hfp failed: {e}")

    def switch_to_a2dp(self):
        """Request HFP→A2DP profile switch. Fires A2DP_ACTIVE when BlueZ confirms."""
        if not self._active_mac:
            return
        try:
            self._set_profile(A2DP_UUID)
        except Exception as e:
            logger.error(f"switch_to_a2dp failed: {e}")

    def _set_profile(self, uuid: str):
        if self._device_proxy:
            if uuid == HFP_UUID:
                self._device_proxy.ConnectProfile(HFP_UUID)
            else:
                self._device_proxy.DisconnectProfile(HFP_UUID)

    def start(self):
        """Start D-Bus signal monitoring in a background thread."""
        if not self._bus:
            return
        t = threading.Thread(target=self._watch_signals, daemon=True)
        t.start()

    def _watch_signals(self):
        """Subscribe to BlueZ signals for connect/disconnect and profile changes."""
        try:
            obj_manager = self._bus.get_proxy(BLUEZ_SERVICE, "/")
            obj_manager.InterfacesAdded.connect(self._on_interfaces_added)
            obj_manager.InterfacesRemoved.connect(self._on_interfaces_removed)

            # Subscribe to PropertiesChanged on the active device to detect
            # when the A2DP→HFP profile switch completes. BlueZ updates the
            # device's "ActiveProfile" or transport state when the switch is done.
            if self._active_mac:
                path = "/org/bluez/hci0/dev_" + self._active_mac.replace(":", "_")
                device = self._bus.get_proxy(BLUEZ_SERVICE, path)
                device.PropertiesChanged.connect(self._on_properties_changed)
        except Exception as e:
            logger.error(f"BlueZ signal watch failed: {e}")

    def _on_properties_changed(self, iface: str, changed: dict, invalidated: list):
        """Handle BlueZ property changes — fires HFP_ACTIVE / A2DP_ACTIVE events."""
        if iface != DEVICE_IFACE:
            return
        # BlueZ sets Connected=True and updates transport UUID when profile switches
        uuids = changed.get("UUIDs", [])
        if uuids:
            if HFP_UUID in uuids:
                logger.info("HFP profile active")
                self._fire(Event.HFP_ACTIVE)
            elif A2DP_UUID in uuids and HFP_UUID not in uuids:
                logger.info("A2DP profile active")
                self._fire(Event.A2DP_ACTIVE)

    def _on_interfaces_added(self, path, interfaces):
        if DEVICE_IFACE in interfaces:
            props = interfaces[DEVICE_IFACE]
            if props.get("Connected", False):
                logger.info(f"BT device connected: {path}")
                self._fire(Event.HEADSET_CONNECTED)

    def _on_interfaces_removed(self, path, interfaces):
        if DEVICE_IFACE in interfaces:
            logger.info(f"BT device disconnected: {path}")
            self._fire(Event.HEADSET_DISCONNECTED)
