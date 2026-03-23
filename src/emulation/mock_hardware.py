"""macOS / development emulation layer for MiniHop hardware dependencies.

Call ``install()`` once — **before** any hardware module imports — to activate:

* **BlueZ D-Bus** – :class:`MockSystemMessageBus` simulates a connected
  headset and fires realistic HFP / A2DP / connect / disconnect events on
  demand via :meth:`EmulationState.inject_headset_connected` etc.

* **PipeWire** – ``subprocess.run`` is monkey-patched to intercept
  ``pw-dump``, ``pw-link``, and ``pw-metadata`` calls; all other subprocess
  calls pass through untouched.  :class:`~src.audio_router.AudioRouter` and
  :func:`~src.healthcheck.collect` both see a fully-populated node graph.

* **GPIO** – :class:`MockButton` / :class:`MockLED` replace the ``gpiozero``
  module; button state is readable and triggerable via the emulation REST API
  or programmatic calls.

* **pyudev** – :class:`MockUdevMonitor` keeps
  :class:`~src.headset_monitor.HeadsetMonitor` alive and accepts injected
  USB plug/unplug events.
"""

from __future__ import annotations

import json
import logging
import queue
import subprocess as _real_subprocess
import sys
import threading
import time
import types
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── BlueZ UUID constants (duplicated here to avoid import-time circular deps) ──
_HFP_UUID = "0000111e-0000-1000-8000-00805f9b34fb"
_A2DP_UUID = "0000110b-0000-1000-8000-00805f9b34fb"
_DEVICE_IFACE = "org.bluez.Device1"

_MOCK_BT_MAC = "AA:BB:CC:DD:EE:FF"

# ── Mock PipeWire node table (matches AudioRouter._get_nodes() detection) ─────
_MOCK_PW_NODES: List[Dict[str, Any]] = [
    {
        "id": 10,
        "type": "PipeWire:Interface:Node",
        "props": {
            "node.name": "alsa_input.xlr-interface.analog-stereo",
            "media.class": "Audio/Source",
            "node.description": "XLR/Line Input (Emulated)",
        },
    },
    {
        "id": 11,
        "type": "PipeWire:Interface:Node",
        "props": {
            "node.name": "alsa_output.xlr-interface.analog-stereo",
            "media.class": "Audio/Sink",
            "node.description": "XLR/Line Output (Emulated)",
        },
    },
    {
        "id": 20,
        "type": "PipeWire:Interface:Node",
        "props": {
            "node.name": "bluez_input.hfp.source",
            "media.class": "Audio/Source",
            "node.description": "BT HFP Mic (Emulated)",
        },
    },
    {
        "id": 21,
        "type": "PipeWire:Interface:Node",
        "props": {
            "node.name": "bluez_output.hfp.sink",
            "media.class": "Audio/Sink",
            "node.description": "BT HFP Speaker (Emulated)",
        },
    },
    {
        "id": 22,
        "type": "PipeWire:Interface:Node",
        "props": {
            "node.name": "bluez_output.a2dp.sink",
            "media.class": "Audio/Sink",
            "node.description": "BT A2DP Sink (Emulated)",
        },
    },
    {
        "id": 30,
        "type": "PipeWire:Interface:Node",
        "props": {
            "node.name": "jabra_dect_source.analog-mono",
            "media.class": "Audio/Source",
            "node.description": "DECT Mic (Emulated)",
        },
    },
    {
        "id": 31,
        "type": "PipeWire:Interface:Node",
        "props": {
            "node.name": "jabra_dect_sink.analog-mono",
            "media.class": "Audio/Sink",
            "node.description": "DECT Speaker (Emulated)",
        },
    },
]


# ── Signal helper ──────────────────────────────────────────────────────────────

class MockSignal:
    """Minimal dasbus signal shim: supports ``.connect(cb)`` and ``.emit(*args)``."""

    def __init__(self, name: str = "") -> None:
        self._name = name
        self._callbacks: List[Callable] = []

    def connect(self, cb: Callable) -> None:
        self._callbacks.append(cb)

    def emit(self, *args: Any) -> None:
        for cb in self._callbacks:
            try:
                cb(*args)
            except Exception as exc:
                logger.warning("[EMULATION] Signal %s callback error: %s", self._name, exc)


# ── BlueZ D-Bus mocks ──────────────────────────────────────────────────────────

class MockBluezDeviceProxy:
    """Emulates ``org.bluez.Device1`` (profile switching + PropertiesChanged)."""

    def __init__(self, path: str, state: "EmulationState") -> None:
        self._path = path
        self._state = state
        self.PropertiesChanged = MockSignal("PropertiesChanged")
        state._register_device_proxy(path, self)

    def ConnectProfile(self, uuid: str) -> None:
        logger.info("[EMULATION] ConnectProfile(%s…) on %s", uuid[:8], self._path)
        self._state.bt_active_profile = "hfp"
        # Short async delay mirrors real BlueZ HFP switch latency
        def _confirm() -> None:
            time.sleep(0.3)
            self.PropertiesChanged.emit(_DEVICE_IFACE, {"UUIDs": [_HFP_UUID]}, [])

        threading.Thread(target=_confirm, daemon=True, name="emu-hfp-confirm").start()

    def DisconnectProfile(self, uuid: str) -> None:
        logger.info("[EMULATION] DisconnectProfile(%s…) on %s", uuid[:8], self._path)
        self._state.bt_active_profile = "a2dp"

        def _confirm() -> None:
            time.sleep(0.3)
            self.PropertiesChanged.emit(_DEVICE_IFACE, {"UUIDs": [_A2DP_UUID]}, [])

        threading.Thread(target=_confirm, daemon=True, name="emu-a2dp-confirm").start()


class MockBluezRootProxy:
    """Emulates the BlueZ root object manager at ``/``."""

    def __init__(self, state: "EmulationState") -> None:
        self._state = state
        self.InterfacesAdded = MockSignal("InterfacesAdded")
        self.InterfacesRemoved = MockSignal("InterfacesRemoved")
        state._root_proxy = self

    def GetManagedObjects(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "/org/bluez/hci0": {
                "org.bluez.Adapter1": {
                    "Powered": self._state.bt_adapter_powered,
                    "Address": "AA:BB:CC:DD:EE:00",
                    "Name": "MiniHop-Emulated",
                }
            }
        }
        for dev in self._state.bt_connected_devices:
            mac_path = dev["mac"].replace(":", "_")
            path = f"/org/bluez/hci0/dev_{mac_path}"
            result[path] = {
                _DEVICE_IFACE: {
                    "Connected": True,
                    "Address": dev["mac"],
                    "Name": dev.get("name", "Emulated Headset"),
                    "UUIDs": dev.get("uuids", [_HFP_UUID, _A2DP_UUID]),
                }
            }
        return result


class MockSystemMessageBus:
    """Emulates ``dasbus.connection.SystemMessageBus``."""

    def __init__(self) -> None:
        # Per-bus proxy cache so signal subscriptions survive multiple get_proxy() calls
        self._proxies: Dict[str, Any] = {}

    def get_proxy(self, service: str, path: str) -> Any:
        if path not in self._proxies:
            if path == "/":
                self._proxies[path] = MockBluezRootProxy(_state)
            else:
                self._proxies[path] = MockBluezDeviceProxy(path, _state)
        return self._proxies[path]


# ── gpiozero mocks ─────────────────────────────────────────────────────────────

class MockButton:
    """Emulates ``gpiozero.Button`` — wired to :class:`EmulationState`."""

    def __init__(self, pin: int, pull_up: bool = True,
                 bounce_time: Optional[float] = None) -> None:
        self.pin = pin
        self.pull_up = pull_up
        self.is_pressed: bool = False
        self.when_pressed: Optional[Callable] = None
        self.when_released: Optional[Callable] = None
        _state._register_button(pin, self)

    def close(self) -> None:
        pass


class MockLED:
    """Emulates ``gpiozero.LED`` — pattern readable via emulation API."""

    def __init__(self, pin: int) -> None:
        self.pin = pin
        self._pattern: str = "off"
        _state._register_led(pin, self)

    def on(self) -> None:
        self._pattern = "solid"
        _state.led_pattern = "solid"

    def off(self) -> None:
        self._pattern = "off"
        _state.led_pattern = "off"

    def blink(self, on_time: float = 1.0, off_time: float = 1.0, **_kw: Any) -> None:
        self._pattern = f"blink({on_time:.1f}/{off_time:.1f})"
        _state.led_pattern = self._pattern


# ── pyudev mocks ───────────────────────────────────────────────────────────────

class MockUdevDevice:
    """Minimal pyudev Device shim for inject_dect_plug / inject_dect_unplug."""

    def __init__(self, action: str, vendor: str = "jabra",
                 model: str = "dect-headset") -> None:
        self.action = action
        self.subsystem = "usb"
        self._props = {"ID_VENDOR": vendor, "ID_MODEL": model}

    def get(self, key: str, default: str = "") -> str:
        return self._props.get(key, default)


class MockUdevMonitor:
    """Minimal pyudev Monitor shim — blocks on a queue; returns None to stop."""

    def __init__(self) -> None:
        pass

    @classmethod
    def from_netlink(cls, context: Any) -> "MockUdevMonitor":
        return cls()

    def filter_by(self, **_kw: Any) -> None:
        pass

    def poll(self) -> Optional[MockUdevDevice]:
        """Block until an event is available; returning None stops the iterator."""
        return _state._usb_event_queue.get()


class MockUdevContext:
    pass


# ── subprocess interceptor ─────────────────────────────────────────────────────

def _pw_dump_handler(cmd: List[str], *_a: Any, **_kw: Any) -> "_real_subprocess.CompletedProcess[bytes]":
    return _real_subprocess.CompletedProcess(
        args=cmd, returncode=0,
        stdout=json.dumps(_state.pipewire_nodes).encode(),
        stderr=b"",
    )


def _pw_link_handler(cmd: List[str], *_a: Any, **_kw: Any) -> "_real_subprocess.CompletedProcess[bytes]":
    if "--list" in cmd:
        lines = [f"{s} -> {d}" for s, d in _state.pipewire_links]
        out = "\n".join(lines) + ("\n" if lines else "")
        return _real_subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout=out.encode(), stderr=b""
        )

    if "--disconnect" in cmd:
        idx = cmd.index("--disconnect")
        if idx + 2 < len(cmd):
            src, dst = cmd[idx + 1], cmd[idx + 2]
            try:
                _state.pipewire_links.remove((src, dst))
                logger.debug("[EMULATION] pw-link --disconnect %s -> %s", src, dst)
            except ValueError:
                pass
        return _real_subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout=b"", stderr=b""
        )

    # pw-link <src_id> <dst_id>
    if len(cmd) >= 3:
        src, dst = cmd[1], cmd[2]
        _state.pipewire_links.append((src, dst))
        logger.debug("[EMULATION] pw-link %s -> %s", src, dst)
    return _real_subprocess.CompletedProcess(
        args=cmd, returncode=0, stdout=b"", stderr=b""
    )


def _pw_metadata_handler(cmd: List[str], *_a: Any, **_kw: Any) -> "_real_subprocess.CompletedProcess[bytes]":
    logger.debug("[EMULATION] pw-metadata %s", " ".join(cmd[1:]))
    return _real_subprocess.CompletedProcess(
        args=cmd, returncode=0, stdout=b"", stderr=b""
    )


def _bluetoothctl_handler(cmd: List[str], *_a: Any, **_kw: Any) -> "_real_subprocess.CompletedProcess[bytes]":
    if "show" in cmd:
        out = "Controller AA:BB:CC:DD:EE:00 (public)\n\tPowered: yes\n"
    elif "devices" in cmd:
        lines = [f"Device {d['mac']} {d['name']}" for d in _state.bt_connected_devices]
        out = "\n".join(lines)
    else:
        out = ""
    return _real_subprocess.CompletedProcess(
        args=cmd, returncode=0, stdout=out.encode(), stderr=b""
    )


_SUBPROCESS_HANDLERS: Dict[str, Callable] = {
    "pw-dump": _pw_dump_handler,
    "pw-link": _pw_link_handler,
    "pw-metadata": _pw_metadata_handler,
    "bluetoothctl": _bluetoothctl_handler,
}

_original_subprocess_run = _real_subprocess.run


def _patched_subprocess_run(cmd: Any, *args: Any, **kwargs: Any) -> "_real_subprocess.CompletedProcess[Any]":
    prog = cmd[0] if isinstance(cmd, (list, tuple)) and cmd else None
    if prog and prog in _SUBPROCESS_HANDLERS:
        return _SUBPROCESS_HANDLERS[prog](cmd, *args, **kwargs)
    return _original_subprocess_run(cmd, *args, **kwargs)


# ── Emulation state singleton ──────────────────────────────────────────────────

class EmulationState:
    """Single source of truth for all emulated hardware state.

    Accessible globally via :func:`get_state`.  The web emulation routes and
    the healthcheck both read from this object.
    """

    def __init__(self) -> None:
        self.bt_adapter_powered: bool = True
        self.bt_active_profile: str = "a2dp"
        self.bt_connected_devices: List[Dict[str, Any]] = [
            {
                "mac": _MOCK_BT_MAC,
                "name": "Emulated Headset",
                "uuids": [_HFP_UUID, _A2DP_UUID],
            }
        ]
        self.pipewire_nodes: List[Dict[str, Any]] = list(_MOCK_PW_NODES)
        self.pipewire_links: List[Tuple[str, str]] = []
        self.led_pattern: str = "off"

        self._buttons: Dict[int, MockButton] = {}
        self._leds: Dict[int, MockLED] = {}
        self._root_proxy: Optional[MockBluezRootProxy] = None
        self._device_proxies: Dict[str, MockBluezDeviceProxy] = {}
        self._usb_event_queue: "queue.Queue[Optional[MockUdevDevice]]" = queue.Queue()

    # ── Registration (called by mock constructors) ─────────────────────────

    def _register_button(self, pin: int, btn: MockButton) -> None:
        self._buttons[pin] = btn

    def _register_led(self, pin: int, led: MockLED) -> None:
        self._leds[pin] = led

    def _register_device_proxy(self, path: str, proxy: MockBluezDeviceProxy) -> None:
        self._device_proxies[path] = proxy

    # ── GPIO triggers ──────────────────────────────────────────────────────

    def trigger_ptt_press(self) -> None:
        btn = self._buttons.get(26)
        if btn:
            btn.is_pressed = True
            if btn.when_pressed:
                btn.when_pressed()
        logger.debug("[EMULATION] PTT pressed")

    def trigger_ptt_release(self) -> None:
        btn = self._buttons.get(26)
        if btn:
            btn.is_pressed = False
            if btn.when_released:
                btn.when_released()
        logger.debug("[EMULATION] PTT released")

    def trigger_mode_press(self) -> None:
        btn = self._buttons.get(21)
        if btn and btn.when_pressed:
            btn.when_pressed()
        logger.debug("[EMULATION] MODE button pressed")

    # ── BlueZ event injectors ──────────────────────────────────────────────

    def inject_headset_connected(self) -> None:
        """Simulate a BT headset connecting (fires InterfacesAdded)."""
        if self._root_proxy is None:
            logger.warning(
                "[EMULATION] inject_headset_connected: root proxy not yet registered "
                "(BT signal watch not started)"
            )
            return
        dev = self.bt_connected_devices[0] if self.bt_connected_devices else {"mac": _MOCK_BT_MAC}
        mac_path = dev["mac"].replace(":", "_")
        path = f"/org/bluez/hci0/dev_{mac_path}"
        logger.info("[EMULATION] Injecting BT headset connected: %s", dev["mac"])
        self._root_proxy.InterfacesAdded.emit(
            path,
            {
                _DEVICE_IFACE: {
                    "Connected": True,
                    "Address": dev["mac"],
                    "Name": dev.get("name", "Emulated Headset"),
                    "UUIDs": dev.get("uuids", [_HFP_UUID, _A2DP_UUID]),
                }
            },
        )

    def inject_headset_disconnected(self) -> None:
        """Simulate a BT headset disconnecting (fires InterfacesRemoved)."""
        if self._root_proxy is None:
            return
        dev = self.bt_connected_devices[0] if self.bt_connected_devices else {"mac": _MOCK_BT_MAC}
        mac_path = dev["mac"].replace(":", "_")
        path = f"/org/bluez/hci0/dev_{mac_path}"
        logger.info("[EMULATION] Injecting BT headset disconnected: %s", dev["mac"])
        self._root_proxy.InterfacesRemoved.emit(path, [_DEVICE_IFACE])

    # ── DECT / USB event injectors ─────────────────────────────────────────

    def inject_dect_plug(self, vendor: str = "jabra", model: str = "dect-headset") -> None:
        logger.info("[EMULATION] Injecting DECT plug: %s %s", vendor, model)
        self._usb_event_queue.put(MockUdevDevice("add", vendor, model))

    def inject_dect_unplug(self, vendor: str = "jabra", model: str = "dect-headset") -> None:
        logger.info("[EMULATION] Injecting DECT unplug: %s %s", vendor, model)
        self._usb_event_queue.put(MockUdevDevice("remove", vendor, model))

    # ── Serialisation for the emulation REST API ───────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        ptt_btn = self._buttons.get(26)
        led_obj = self._leds.get(17)
        return {
            "emulation_mode": True,
            "bluetooth": {
                "adapter_powered": self.bt_adapter_powered,
                "active_profile": self.bt_active_profile,
                "connected_devices": self.bt_connected_devices,
            },
            "pipewire": {
                "nodes": [
                    {
                        "id": n["id"],
                        "name": n["props"].get("node.name", ""),
                        "media_class": n["props"].get("media.class", ""),
                        "description": n["props"].get("node.description", ""),
                    }
                    for n in self.pipewire_nodes
                ],
                "links": [{"src": s, "dst": d} for s, d in self.pipewire_links],
            },
            "gpio": {
                "ptt_pressed": ptt_btn.is_pressed if ptt_btn else False,
                "led_pattern": led_obj._pattern if led_obj else self.led_pattern,
            },
        }

    # ── Auto-connect on boot ───────────────────────────────────────────────

    def _schedule_auto_connect(self, delay: float = 2.0) -> None:
        """Fire a headset-connected event after *delay* seconds.

        The delay gives the BT signal watch thread time to subscribe to
        InterfacesAdded before the event fires.
        """
        def _run() -> None:
            time.sleep(delay)
            self.inject_headset_connected()

        threading.Thread(target=_run, daemon=True, name="emu-auto-connect").start()


# Module-level singleton — created before install() so mock constructors can use it.
_state = EmulationState()


def get_state() -> EmulationState:
    """Return the global :class:`EmulationState` singleton."""
    return _state


# ── Public install API ─────────────────────────────────────────────────────────

_installed = False


def install() -> None:
    """Patch ``sys.modules`` and ``subprocess.run`` for hardware-free operation.

    Must be called **before** importing any of:
    ``src.bluetooth_manager``, ``src.gpio_handler``, ``src.led_manager``,
    ``src.audio_router``, ``src.headset_monitor``, ``src.healthcheck``.
    Idempotent — safe to call multiple times.
    """
    global _installed
    if _installed:
        return
    _installed = True

    logger.info("[EMULATION] Installing mock hardware (BlueZ D-Bus, PipeWire, GPIO, pyudev)")

    # ── gpiozero ──────────────────────────────────────────────────────────
    _gpiozero = types.ModuleType("gpiozero")
    _gpiozero.Button = MockButton  # type: ignore[attr-defined]
    _gpiozero.LED = MockLED  # type: ignore[attr-defined]
    sys.modules["gpiozero"] = _gpiozero

    # ── dasbus ────────────────────────────────────────────────────────────
    _dasbus = types.ModuleType("dasbus")
    _dasbus_conn = types.ModuleType("dasbus.connection")
    _dasbus_conn.SystemMessageBus = MockSystemMessageBus  # type: ignore[attr-defined]
    sys.modules["dasbus"] = _dasbus
    sys.modules["dasbus.connection"] = _dasbus_conn

    # ── pyudev ────────────────────────────────────────────────────────────
    _pyudev = types.ModuleType("pyudev")
    _pyudev.Context = MockUdevContext  # type: ignore[attr-defined]
    _pyudev.Monitor = MockUdevMonitor  # type: ignore[attr-defined]
    sys.modules["pyudev"] = _pyudev

    # ── subprocess (pw-dump / pw-link / pw-metadata / bluetoothctl only) ──
    _real_subprocess.run = _patched_subprocess_run  # type: ignore[method-assign]

    # Schedule an initial simulated BT headset-connected event so the state
    # machine starts in IDLE rather than NO_HEADSET.
    _state._schedule_auto_connect(delay=2.0)

    logger.info("[EMULATION] Mock hardware active — headset-connected fires in ~2 s")
