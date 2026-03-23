# src/led_manager.py
from gpiozero import LED
from src.state_machine import State

# Blink parameters for non-solid patterns
BLINK_PATTERNS = {
    "slow_blink":  dict(on_time=1.0, off_time=1.0),
    "fast_blink":  dict(on_time=0.2, off_time=0.2),
    "amber_blink": dict(on_time=0.5, off_time=0.5),
}


class LedManager:
    def __init__(self, pin: int = 17):
        self._led = LED(pin)
        self._current = None

    def update(self, state: State, latched: bool = False):
        pattern = self._resolve(state, latched)
        if pattern == self._current:
            return
        self._current = pattern
        self._led.off()
        if pattern == "solid":
            self._led.on()
        else:
            p = BLINK_PATTERNS[pattern]
            self._led.blink(on_time=p["on_time"], off_time=p["off_time"])

    def _resolve(self, state: State, latched: bool) -> str:
        if state == State.NO_HEADSET:
            return "slow_blink"
        if state == State.SWITCHING:
            return "amber_blink"
        if state == State.TALK:
            return "fast_blink" if latched else "solid"
        if state == State.IDLE:
            return "slow_blink"
        return "slow_blink"
