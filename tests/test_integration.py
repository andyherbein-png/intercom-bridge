# tests/test_integration.py
import time
import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch


def test_full_dect_ptt_cycle():
    """Full Dynamic mode DECT PTT cycle: press → TALK → release → hold → IDLE."""
    with patch("src.led_manager.LED"), \
         patch("src.gpio_handler.Button"), \
         patch("subprocess.run"):

        from src.config import Config
        from src.state_machine import StateMachine, State, Event, HeadsetType
        from src.audio_router import AudioRouter
        from src.led_manager import LedManager

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            cfg_path = f.name
        try:
            cfg = Config(cfg_path)
            cfg.hold_time_ms = 100
            sm = StateMachine(cfg)
            router = AudioRouter()
            led = LedManager(pin=17)

            state_log = []
            sm.on_state_change(state_log.append)
            sm.on_state_change(led.update)

            sm.set_headset_type(HeadsetType.DECT)
            sm.handle(Event.HEADSET_CONNECTED)
            assert sm.state == State.IDLE

            sm.handle(Event.PTT_PRESS)
            assert sm.state == State.TALK

            sm.handle(Event.PTT_RELEASE)
            time.sleep(0.15)
            sm.tick()
            assert sm.state == State.IDLE

            assert State.TALK in state_log
            assert State.IDLE in state_log
        finally:
            os.unlink(cfg_path)


def test_full_bt_latch_cycle():
    """Latch mode BT: press latches HFP on, second press releases."""
    with patch("src.led_manager.LED"), \
         patch("src.gpio_handler.Button"), \
         patch("subprocess.run"):

        from src.config import Config
        from src.state_machine import StateMachine, State, Event, HeadsetType

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            cfg_path = f.name
        try:
            cfg = Config(cfg_path)
            cfg.operation_mode = "latch"
            sm = StateMachine(cfg)

            sm.set_headset_type(HeadsetType.BT)
            sm.handle(Event.HEADSET_CONNECTED)
            sm.handle(Event.PTT_PRESS)
            assert sm.state == State.SWITCHING

            sm.handle(Event.HFP_ACTIVE)
            assert sm.state == State.TALK

            sm.handle(Event.PTT_PRESS)   # second press disengages
            assert sm.state == State.IDLE
        finally:
            os.unlink(cfg_path)
