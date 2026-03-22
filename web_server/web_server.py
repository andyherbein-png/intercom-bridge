# web_server/web_server.py
"""
MiniHop Flask web server.
Provides a C64-themed dashboard and REST API for config/status,
plus the hidden chess easter egg with SSE audio-exit integration.
"""
import json
import logging
import queue
import sys
import os
import threading
from typing import List

from flask import Flask, Response, jsonify, render_template, request, stream_with_context

# Allow importing src modules when run from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import Config

logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── Config (shared with main process via Config object) ─────────────────────
_config: Config = None
_get_state = None          # callable() → str  (set by main.py)
_chess_event_listeners: List[queue.SimpleQueue] = []


def init(config: Config, get_state_fn=None):
    """Call from main.py to wire the web server to the running system."""
    global _config, _get_state
    _config = config
    _get_state = get_state_fn


def notify_chess_exit():
    """Call from state_machine callback on any audio event to kick chess players out."""
    for q in list(_chess_event_listeners):
        try:
            q.put_nowait("EXIT")
        except Exception:
            pass


def start(host="0.0.0.0", port=5000):
    """Start Flask in a daemon thread."""
    t = threading.Thread(
        target=lambda: app.run(host=host, port=port, threaded=True, use_reloader=False),
        daemon=True,
    )
    t.start()
    logger.info("Web UI started at http://%s:%d", host, port)


# ── Dashboard ────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    cfg = _config
    state = _get_state() if _get_state else "IDLE"
    return render_template("index.html", cfg=cfg, state=state)


# ── REST API ─────────────────────────────────────────────────────────────────


@app.route("/api/status")
def api_status():
    cfg = _config
    state = _get_state() if _get_state else "IDLE"
    return jsonify({
        "state": state,
        "operation_mode": cfg.operation_mode if cfg else "dynamic",
        "bt_active_mac": cfg.bt_active_mac if cfg else "",
        "hold_time_ms": cfg.hold_time_ms if cfg else 3000,
    })


@app.route("/api/config", methods=["GET"])
def api_config_get():
    cfg = _config
    if not cfg:
        return jsonify({"error": "not initialized"}), 503
    return jsonify({
        "operation_mode": cfg.operation_mode,
        "hold_time_ms": cfg.hold_time_ms,
        "bt_active_mac": cfg.bt_active_mac,
        "bt_max_paired_devices": cfg.bt_max_paired_devices,
        "sidetone": cfg.sidetone,
        "ble_ptt_enabled": cfg.ble_ptt_enabled,
        "ble_ptt_mac": cfg.ble_ptt_mac,
        "hotspot_ssid": cfg.hotspot_ssid,
        "hotspot_password": cfg.hotspot_password,
        "hotspot_pairing_window_s": cfg.hotspot_pairing_window_s,
        "profiles": {k: cfg.get_profile(k) for k in
                     ("xlr5_bt", "xlr5_dect", "wire4_bt", "wire4_dect")},
    })


@app.route("/api/config", methods=["POST"])
def api_config_post():
    cfg = _config
    if not cfg:
        return jsonify({"error": "not initialized"}), 503
    data = request.get_json(force=True, silent=True) or {}

    allowed_modes = ("dynamic", "latch", "permanent")
    if "operation_mode" in data and data["operation_mode"] in allowed_modes:
        cfg.operation_mode = data["operation_mode"]

    if "hold_time_ms" in data:
        try:
            cfg.hold_time_ms = int(data["hold_time_ms"])
        except (ValueError, TypeError):
            pass

    if "ble_ptt_mac" in data:
        cfg.ble_ptt_mac = str(data["ble_ptt_mac"])

    if "profiles" in data and isinstance(data["profiles"], dict):
        for key, val in data["profiles"].items():
            if isinstance(val, dict):
                cfg.set_profile(
                    key,
                    input_db=val.get("input_db"),
                    output_db=val.get("output_db"),
                )

    cfg.save()
    return jsonify({"ok": True})


# ── Chess Easter Egg ─────────────────────────────────────────────────────────


@app.route("/chess")
def chess_page():
    return render_template("chess.html")


@app.route("/chess/events")
def chess_events():
    def generate():
        q = queue.SimpleQueue()
        _chess_event_listeners.append(q)
        try:
            while True:
                try:
                    msg = q.get(timeout=25)
                    yield "data: {}\n\n".format(msg)
                except queue.Empty:
                    yield "data: KEEPALIVE\n\n"
        finally:
            try:
                _chess_event_listeners.remove(q)
            except ValueError:
                pass

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Dev entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Standalone dev mode: load config from default path or create defaults
    _config = Config()
    _get_state = lambda: "IDLE"
    app.run(host="127.0.0.1", port=5000, debug=False)
