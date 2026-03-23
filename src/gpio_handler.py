# src/gpio_handler.py
from gpiozero import Button
from typing import Callable, Optional


class GpioHandler:
    def __init__(self, ptt_pin: int = 26, mode_pin: int = 21):
        self._ptt = Button(ptt_pin, pull_up=True, bounce_time=0.05)
        self._mode = Button(mode_pin, pull_up=True, bounce_time=0.05)
        self._ptt_press_cb: Optional[Callable] = None
        self._ptt_release_cb: Optional[Callable] = None
        self._mode_cb: Optional[Callable] = None

        self._ptt.when_pressed = self._on_ptt_press
        self._ptt.when_released = self._on_ptt_release
        self._mode.when_pressed = self._on_mode

    def on_ptt_press(self, cb: Callable):
        self._ptt_press_cb = cb

    def on_ptt_release(self, cb: Callable):
        self._ptt_release_cb = cb

    def on_mode_change(self, cb: Callable):
        self._mode_cb = cb

    def _on_ptt_press(self):
        if self._ptt_press_cb:
            self._ptt_press_cb()

    def _on_ptt_release(self):
        if self._ptt_release_cb:
            self._ptt_release_cb()

    def _on_mode(self):
        if self._mode_cb:
            self._mode_cb()
