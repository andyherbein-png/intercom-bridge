"""Flask Blueprint for emulation control endpoints.

Registered automatically by ``web_server.py`` when ``EMULATION_MODE=1``.

Endpoints
---------
``GET  /api/emulation/state``
    Full snapshot of emulated hardware state (BT, PipeWire nodes/links, GPIO).

``POST /api/emulation/ptt``
    Simulate PTT button.  Body: ``{"action": "press"|"release"}``

``POST /api/emulation/mode``
    Simulate a single hardware mode-cycle button press.

``POST /api/emulation/headset``
    Simulate a BT headset connect/disconnect.
    Body: ``{"action": "connect"|"disconnect"}``

``POST /api/emulation/dect``
    Simulate a DECT dongle USB plug/unplug.
    Body: ``{"action": "plug"|"unplug", "vendor": "jabra", "model": "dect-headset"}``
"""

from flask import Blueprint, jsonify, request

from src.emulation.mock_hardware import get_state

emulation_bp = Blueprint("emulation", __name__)


@emulation_bp.route("/api/emulation/state")
def emu_state():
    """Return a full snapshot of the emulated hardware state."""
    return jsonify(get_state().to_dict())


@emulation_bp.route("/api/emulation/ptt", methods=["POST"])
def emu_ptt():
    """Simulate a PTT button press or release.

    Body: ``{"action": "press" | "release"}``
    """
    data = request.get_json(force=True, silent=True) or {}
    action = data.get("action", "press")
    state = get_state()
    if action == "press":
        state.trigger_ptt_press()
    elif action == "release":
        state.trigger_ptt_release()
    else:
        return jsonify({"error": f"unknown action: {action!r}"}), 400
    return jsonify({"ok": True, "action": action})


@emulation_bp.route("/api/emulation/mode", methods=["POST"])
def emu_mode():
    """Simulate a single hardware mode-cycle button press."""
    get_state().trigger_mode_press()
    return jsonify({"ok": True})


@emulation_bp.route("/api/emulation/headset", methods=["POST"])
def emu_headset():
    """Simulate a BT headset connect or disconnect event.

    Body: ``{"action": "connect" | "disconnect"}``
    """
    data = request.get_json(force=True, silent=True) or {}
    action = data.get("action", "connect")
    state = get_state()
    if action == "connect":
        state.inject_headset_connected()
    elif action == "disconnect":
        state.inject_headset_disconnected()
    else:
        return jsonify({"error": f"unknown action: {action!r}"}), 400
    return jsonify({"ok": True, "action": action})


@emulation_bp.route("/api/emulation/dect", methods=["POST"])
def emu_dect():
    """Simulate a DECT dongle USB plug or unplug event.

    Body: ``{"action": "plug"|"unplug", "vendor": "jabra", "model": "dect-headset"}``
    """
    data = request.get_json(force=True, silent=True) or {}
    action = data.get("action", "plug")
    vendor = data.get("vendor", "jabra")
    model = data.get("model", "dect-headset")
    state = get_state()
    if action == "plug":
        state.inject_dect_plug(vendor, model)
    elif action == "unplug":
        state.inject_dect_unplug(vendor, model)
    else:
        return jsonify({"error": f"unknown action: {action!r}"}), 400
    return jsonify({"ok": True, "action": action, "vendor": vendor, "model": model})
