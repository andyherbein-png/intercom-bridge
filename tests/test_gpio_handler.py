# tests/test_gpio_handler.py
import pytest
from unittest.mock import MagicMock, patch
from src.gpio_handler import GpioHandler


@pytest.fixture
def handler():
    with patch("src.gpio_handler.Button") as MockButton:
        mock_ptt = MagicMock()
        mock_mode = MagicMock()
        MockButton.side_effect = [mock_ptt, mock_mode]
        h = GpioHandler(ptt_pin=26, mode_pin=21)
        yield h, mock_ptt, mock_mode


def test_ptt_press_fires_callback(handler):
    h, mock_ptt, _ = handler
    cb = MagicMock()
    h.on_ptt_press(cb)
    # Simulate button press by calling the registered when_pressed
    mock_ptt.when_pressed()
    cb.assert_called_once()


def test_ptt_release_fires_callback(handler):
    h, mock_ptt, _ = handler
    cb = MagicMock()
    h.on_ptt_release(cb)
    mock_ptt.when_released()
    cb.assert_called_once()


def test_mode_change_fires_callback(handler):
    h, _, mock_mode = handler
    cb = MagicMock()
    h.on_mode_change(cb)
    mock_mode.when_pressed()
    cb.assert_called_once()
