# tests/test_led_manager.py
import pytest
from unittest.mock import MagicMock, patch
from src.state_machine import State
from src.led_manager import LedManager


@pytest.fixture
def led(monkeypatch):
    # Patch gpiozero LED so tests don't need real GPIO
    mock_led = MagicMock()
    with patch("src.led_manager.LED", return_value=mock_led):
        manager = LedManager(pin=17)
        yield manager, mock_led


def test_no_headset_blinks_slow_red(led):
    manager, mock_led = led
    manager.update(State.NO_HEADSET)
    mock_led.blink.assert_called()


def test_talk_dynamic_solid_green(led):
    manager, mock_led = led
    manager.update(State.TALK, latched=False)
    mock_led.on.assert_called()


def test_talk_latched_fast_blink(led):
    manager, mock_led = led
    manager.update(State.TALK, latched=True)
    mock_led.blink.assert_called()


def test_idle_slow_blink(led):
    manager, mock_led = led
    manager.update(State.IDLE)
    mock_led.blink.assert_called()


def test_switching_amber_blink(led):
    manager, mock_led = led
    manager.update(State.SWITCHING)
    mock_led.blink.assert_called()
