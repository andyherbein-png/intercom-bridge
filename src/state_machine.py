# src/state_machine.py
import time
import threading
from enum import Enum, auto
from typing import Callable, List, Optional


class State(Enum):
    NO_HEADSET = auto()
    IDLE = auto()
    SWITCHING = auto()   # BT only: A2DP→HFP in progress
    TALK = auto()


class Event(Enum):
    PTT_PRESS = auto()
    PTT_RELEASE = auto()
    HFP_ACTIVE = auto()       # BlueZ: HFP profile up
    A2DP_ACTIVE = auto()      # BlueZ: A2DP profile up (after TALK→IDLE)
    HEADSET_CONNECTED = auto()
    HEADSET_DISCONNECTED = auto()
    MODE_CHANGE = auto()      # operation_mode changed; re-evaluate


class HeadsetType(Enum):
    NONE = auto()
    BT = auto()
    DECT = auto()


class StateMachine:
    def __init__(self, config):
        self._cfg = config
        self._state = State.NO_HEADSET
        self._headset = HeadsetType.NONE
        self._callbacks: List[Callable] = []
        self._hold_timer: Optional[threading.Timer] = None
        self._ptt_held = False          # track whether PTT is currently down
        self._pending_hold = False      # PTT released during SWITCHING

    @property
    def state(self) -> State:
        return self._state

    def set_headset_type(self, htype: HeadsetType):
        self._headset = htype

    @property
    def headset_type(self) -> HeadsetType:
        return self._headset

    def on_state_change(self, cb: Callable):
        self._callbacks.append(cb)

    def _set_state(self, new_state: State):
        if new_state != self._state:
            self._state = new_state
            for cb in self._callbacks:
                cb(new_state)

    def _cancel_hold_timer(self):
        if self._hold_timer:
            self._hold_timer.cancel()
            self._hold_timer = None

    def _start_hold_timer(self):
        self._cancel_hold_timer()
        delay = self._cfg.hold_time_ms / 1000.0
        self._hold_timer = threading.Timer(delay, self._hold_expired)
        self._hold_timer.daemon = True
        self._hold_timer.start()

    def _hold_expired(self):
        if self._state == State.TALK:
            self._set_state(State.IDLE)

    def tick(self):
        """Call periodically (or after sleep in tests) to process timer expiry."""
        pass  # timer fires on its own thread; tick is a no-op hook for tests

    def handle(self, event: Event):
        mode = self._cfg.operation_mode
        s = self._state

        if event == Event.HEADSET_CONNECTED:
            self._headset_connected()

        elif event == Event.HEADSET_DISCONNECTED:
            self._cancel_hold_timer()
            self._ptt_held = False
            self._pending_hold = False
            self._set_state(State.NO_HEADSET)

        elif event == Event.MODE_CHANGE:
            self._apply_mode()

        elif event == Event.PTT_PRESS:
            self._on_ptt_press(mode, s)

        elif event == Event.PTT_RELEASE:
            self._on_ptt_release(mode, s)

        elif event == Event.HFP_ACTIVE:
            if s == State.SWITCHING:
                self._set_state(State.TALK)
                if self._pending_hold:
                    self._pending_hold = False
                    self._start_hold_timer()

        elif event == Event.A2DP_ACTIVE:
            pass  # audio_router handles rerouting; state already IDLE

    def _headset_connected(self):
        mode = self._cfg.operation_mode
        if mode == "permanent":
            self._set_state(State.TALK)
        else:
            self._set_state(State.IDLE)

    def _apply_mode(self):
        mode = self._cfg.operation_mode
        if mode == "permanent" and self._state in (State.IDLE, State.TALK):
            self._cancel_hold_timer()
            self._set_state(State.TALK)
        elif mode in ("dynamic", "latch") and self._state == State.TALK:
            # Don't yank talk away immediately on mode change; let user PTT again
            pass

    def _on_ptt_press(self, mode: str, s: State):
        if s == State.NO_HEADSET:
            return
        if s == State.SWITCHING:
            return  # ignored during BT profile switch

        if mode == "dynamic":
            if s == State.IDLE:
                self._ptt_held = True
                self._cancel_hold_timer()
                if self._headset == HeadsetType.BT:
                    self._set_state(State.SWITCHING)
                else:
                    self._set_state(State.TALK)
            elif s == State.TALK:
                self._cancel_hold_timer()  # reset hold timer

        elif mode == "latch":
            if s == State.IDLE:
                if self._headset == HeadsetType.BT:
                    self._set_state(State.SWITCHING)
                else:
                    self._set_state(State.TALK)
            elif s == State.TALK:
                self._cancel_hold_timer()
                # Second press: disengage
                self._set_state(State.IDLE)

        elif mode == "permanent":
            pass  # PTT press has no effect in permanent mode

    def _on_ptt_release(self, mode: str, s: State):
        if mode == "dynamic":
            if s == State.SWITCHING:
                self._pending_hold = True  # hold timer starts when HFP_ACTIVE arrives
            elif s == State.TALK:
                self._start_hold_timer()
        # latch and permanent: PTT_RELEASE has no effect
