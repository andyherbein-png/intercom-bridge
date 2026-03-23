#!/usr/bin/env python3
"""src/healthcheck.py — Standalone system health reporter.

Usage::

    python -m src.healthcheck        # via module (preferred; sets sys.path)
    python src/healthcheck.py        # direct invocation

Prints a JSON object with three sections:

* **bluetooth** – BlueZ adapter power state and every currently-connected device,
  queried via D-Bus (dasbus).  Falls back to a ``bluetoothctl`` subprocess when
  D-Bus is unavailable (e.g. development machines).

* **pipewire_nodes** – Active PipeWire nodes discovered via ``pw-dump``, mapped to
  the same logical roles used by :class:`~src.audio_router.AudioRouter`.

* **ptt** – Physical PTT-button state read directly from GPIO (gpiozero).
  Reports ``null`` with an explanatory error string on non-Pi hardware.

Exit codes:
  0 – all subsystems probed without errors
  1 – one or more subsystems reported an error (check each ``.error`` field)
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

# Must match GpioHandler defaults so the healthcheck checks the same pin.
_PTT_PIN = 26


# ── Bluetooth ──────────────────────────────────────────────────────────────────

def _bt_via_dbus() -> dict[str, Any]:
    """Query BlueZ via D-Bus using dasbus (project runtime dependency)."""
    from dasbus.connection import SystemMessageBus  # type: ignore[import]

    bus = SystemMessageBus()
    manager = bus.get_proxy("org.bluez", "/")
    objects: dict = manager.GetManagedObjects()

    adapter_powered: bool | None = None
    connected: list[dict[str, Any]] = []

    for _path, interfaces in objects.items():
        if "org.bluez.Adapter1" in interfaces:
            adapter_powered = bool(
                interfaces["org.bluez.Adapter1"].get("Powered", False)
            )
        elif "org.bluez.Device1" in interfaces:
            props = interfaces["org.bluez.Device1"]
            if props.get("Connected", False):
                connected.append(
                    {
                        "mac": str(props.get("Address", "")),
                        "name": str(props.get("Name", props.get("Address", ""))),
                        "uuids": [str(u) for u in props.get("UUIDs", [])],
                    }
                )

    return {
        "adapter_powered": adapter_powered,
        "connected_devices": connected,
        "source": "dbus",
        "error": None,
    }


def _bt_via_bluetoothctl() -> dict[str, Any]:
    """Query Bluetooth state using the ``bluetoothctl`` CLI (subprocess fallback)."""
    out: dict[str, Any] = {
        "adapter_powered": None,
        "connected_devices": [],
        "source": "bluetoothctl",
        "error": None,
    }
    show = subprocess.run(
        ["bluetoothctl", "show"], capture_output=True, text=True, timeout=4
    )
    for line in show.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("Powered:"):
            out["adapter_powered"] = stripped.split(":", 1)[1].strip().lower() == "yes"
            break

    # ``bluetoothctl devices Connected`` requires BlueZ ≥ 5.64.
    devices_proc = subprocess.run(
        ["bluetoothctl", "devices", "Connected"],
        capture_output=True, text=True, timeout=4,
    )
    connected: list[dict[str, str]] = []
    for line in devices_proc.stdout.splitlines():
        parts = line.strip().split(" ", 2)
        if len(parts) >= 2 and parts[0] == "Device":
            connected.append(
                {"mac": parts[1], "name": parts[2] if len(parts) == 3 else parts[1]}
            )
    out["connected_devices"] = connected
    return out


def _bt_status() -> dict[str, Any]:
    """Return Bluetooth status, trying D-Bus first then falling back to CLI."""
    try:
        return _bt_via_dbus()
    except ImportError:
        pass  # dasbus not installed — try CLI
    except Exception:  # noqa: BLE001
        pass  # D-Bus not available (e.g. macOS dev machine)

    try:
        return _bt_via_bluetoothctl()
    except FileNotFoundError:
        return {
            "adapter_powered": None,
            "connected_devices": [],
            "source": None,
            "error": "neither dasbus nor bluetoothctl is available",
        }
    except subprocess.TimeoutExpired:
        return {
            "adapter_powered": None,
            "connected_devices": [],
            "source": "bluetoothctl",
            "error": "bluetoothctl timed out",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "adapter_powered": None,
            "connected_devices": [],
            "source": "bluetoothctl",
            "error": str(exc),
        }


# ── PipeWire ───────────────────────────────────────────────────────────────────

def _pipewire_nodes() -> dict[str, Any]:
    """Discover active PipeWire nodes via ``pw-dump``, mapped to logical roles.

    Role mapping mirrors :meth:`~src.audio_router.AudioRouter._get_nodes` so the
    output is directly comparable to what the running bridge sees.
    """
    out: dict[str, Any] = {"nodes": {}, "raw_node_count": 0, "error": None}
    try:
        proc = subprocess.run(
            ["pw-dump"], capture_output=True, timeout=3, check=False
        )
        if proc.returncode != 0:
            out["error"] = (
                f"pw-dump exited with code {proc.returncode}: "
                f"{proc.stderr.decode(errors='replace').strip()}"
            )
            return out

        raw: list = json.loads(proc.stdout)
        out["raw_node_count"] = sum(
            1 for n in raw if n.get("type") == "PipeWire:Interface:Node"
        )

        role_map: dict[str, dict[str, str]] = {}
        for node in raw:
            if node.get("type") != "PipeWire:Interface:Node":
                continue
            props = node.get("props", {})
            name: str = props.get("node.name", "")
            nid = str(node.get("id", ""))
            media_class: str = props.get("media.class", "")
            desc: str = props.get("node.description", name)

            if "bluez" in name and "hfp" in name:
                role = "bt_hfp_source" if "Source" in media_class else "bt_hfp_sink"
            elif "bluez" in name and "a2dp" in name:
                role = "bt_a2dp_sink"
            elif "alsa" in name and "input" in name:
                role = "xlr_source"
            elif "alsa" in name and "output" in name:
                role = "xlr_sink"
            elif any(k in name.lower() for k in ("dect", "jabra", "epos")):
                role = "dect_source" if "Source" in media_class else "dect_sink"
            else:
                continue  # unrecognised node — skip

            role_map[role] = {
                "id": nid,
                "name": name,
                "description": desc,
                "media_class": media_class,
            }

        out["nodes"] = role_map

    except subprocess.TimeoutExpired:
        out["error"] = "pw-dump timed out"
    except FileNotFoundError:
        out["error"] = "pw-dump not found — is PipeWire installed?"
    except json.JSONDecodeError as exc:
        out["error"] = f"pw-dump output is not valid JSON: {exc}"
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)

    return out


# ── PTT ────────────────────────────────────────────────────────────────────────

def _ptt_state() -> dict[str, Any]:
    """Read the physical PTT button state from GPIO BCM pin :data:`_PTT_PIN`."""
    out: dict[str, Any] = {"pressed": None, "pin_bcm": _PTT_PIN, "error": None}
    try:
        from gpiozero import Button  # type: ignore[import]

        btn = Button(_PTT_PIN, pull_up=True)
        out["pressed"] = btn.is_pressed
        btn.close()
    except ImportError:
        out["error"] = "gpiozero not available (non-Pi environment)"
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)
    return out


# ── Entry point ────────────────────────────────────────────────────────────────

def collect() -> dict[str, Any]:
    """Collect and return the full health report as a plain dict."""
    return {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "bluetooth": _bt_status(),
        "pipewire_nodes": _pipewire_nodes(),
        "ptt": _ptt_state(),
    }


if __name__ == "__main__":
    report = collect()
    print(json.dumps(report, indent=2))
    errors = [k for k, v in report.items() if isinstance(v, dict) and v.get("error")]
    sys.exit(1 if errors else 0)
