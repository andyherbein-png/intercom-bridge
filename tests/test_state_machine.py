# tests/test_state_machine.py
import time
import pytest
from unittest.mock import MagicMock
from src.state_machine import StateMachine, State, Event, HeadsetType


@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.operation_mode = "dynamic"
    cfg.hold_time_ms = 100  # short for fast tests
    return cfg


@pytest.fixture
def sm(mock_config):
    return StateMachine(mock_config)


# --- Dynamic mode (BT) ---

def test_initial_state_is_idle(sm):
    assert sm.state == State.NO_HEADSET


def test_ptt_press_bt_enters_switching(sm):
    sm.set_headset_type(HeadsetType.BT)
    sm.handle(Event.HEADSET_CONNECTED)
    sm.handle(Event.PTT_PRESS)
    assert sm.state == State.SWITCHING


def test_hfp_active_enters_talk(sm):
    sm.set_headset_type(HeadsetType.BT)
    sm.handle(Event.HEADSET_CONNECTED)
    sm.handle(Event.PTT_PRESS)
    sm.handle(Event.HFP_ACTIVE)
    assert sm.state == State.TALK


def test_ptt_release_during_switching_completes_to_talk_then_holds(sm):
    sm.set_headset_type(HeadsetType.BT)
    sm.handle(Event.HEADSET_CONNECTED)
    sm.handle(Event.PTT_PRESS)
    sm.handle(Event.PTT_RELEASE)   # released before HFP up
    sm.handle(Event.HFP_ACTIVE)   # switch completes anyway
    assert sm.state == State.TALK
    time.sleep(0.15)               # hold_time_ms=100
    sm.tick()
    assert sm.state == State.IDLE


def test_ptt_press_during_switching_is_ignored(sm):
    sm.set_headset_type(HeadsetType.BT)
    sm.handle(Event.HEADSET_CONNECTED)
    sm.handle(Event.PTT_PRESS)
    sm.handle(Event.PTT_PRESS)    # second press while switching
    sm.handle(Event.HFP_ACTIVE)
    assert sm.state == State.TALK  # no crash, normal TALK


def test_hold_timer_returns_to_idle_after_ptt_release(sm):
    sm.set_headset_type(HeadsetType.BT)
    sm.handle(Event.HEADSET_CONNECTED)
    sm.handle(Event.PTT_PRESS)
    sm.handle(Event.HFP_ACTIVE)
    sm.handle(Event.PTT_RELEASE)
    time.sleep(0.15)
    sm.tick()
    assert sm.state == State.IDLE


def test_ptt_press_in_talk_resets_hold_timer(sm):
    sm.set_headset_type(HeadsetType.BT)
    sm.handle(Event.HEADSET_CONNECTED)
    sm.handle(Event.PTT_PRESS)
    sm.handle(Event.HFP_ACTIVE)
    sm.handle(Event.PTT_RELEASE)
    time.sleep(0.06)               # partial hold
    sm.handle(Event.PTT_PRESS)    # resets timer
    sm.handle(Event.PTT_RELEASE)
    time.sleep(0.06)               # would have expired if not reset
    sm.tick()
    assert sm.state == State.TALK  # still in TALK; full hold hasn't elapsed


# --- Dynamic mode (DECT) ---

def test_dect_ptt_skips_switching(sm):
    sm.set_headset_type(HeadsetType.DECT)
    sm.handle(Event.HEADSET_CONNECTED)
    sm.handle(Event.PTT_PRESS)
    assert sm.state == State.TALK  # no SWITCHING for DECT


def test_dect_ptt_release_hold_returns_to_idle(sm):
    sm.set_headset_type(HeadsetType.DECT)
    sm.handle(Event.HEADSET_CONNECTED)
    sm.handle(Event.PTT_PRESS)
    sm.handle(Event.PTT_RELEASE)
    time.sleep(0.15)
    sm.tick()
    assert sm.state == State.IDLE


# --- Latch mode ---

def test_latch_first_press_enters_talk(sm, mock_config):
    mock_config.operation_mode = "latch"
    sm.set_headset_type(HeadsetType.DECT)
    sm.handle(Event.HEADSET_CONNECTED)
    sm.handle(Event.MODE_CHANGE)
    sm.handle(Event.PTT_PRESS)
    assert sm.state == State.TALK


def test_latch_second_press_returns_to_idle(sm, mock_config):
    mock_config.operation_mode = "latch"
    sm.set_headset_type(HeadsetType.DECT)
    sm.handle(Event.HEADSET_CONNECTED)
    sm.handle(Event.MODE_CHANGE)
    sm.handle(Event.PTT_PRESS)
    sm.handle(Event.PTT_PRESS)   # second press disengages
    sm.tick()
    assert sm.state == State.IDLE


# --- Permanent mode ---

def test_permanent_mode_stays_in_talk(sm, mock_config):
    mock_config.operation_mode = "permanent"
    sm.set_headset_type(HeadsetType.DECT)
    sm.handle(Event.HEADSET_CONNECTED)
    sm.handle(Event.MODE_CHANGE)
    assert sm.state == State.TALK


def test_permanent_mode_ptt_release_no_timer(sm, mock_config):
    mock_config.operation_mode = "permanent"
    sm.set_headset_type(HeadsetType.DECT)
    sm.handle(Event.HEADSET_CONNECTED)
    sm.handle(Event.MODE_CHANGE)
    sm.handle(Event.PTT_RELEASE)
    time.sleep(0.15)
    sm.tick()
    assert sm.state == State.TALK


# --- Headset disconnect ---

def test_headset_disconnect_during_switching_aborts(sm):
    sm.set_headset_type(HeadsetType.BT)
    sm.handle(Event.HEADSET_CONNECTED)
    sm.handle(Event.PTT_PRESS)
    assert sm.state == State.SWITCHING
    sm.handle(Event.HEADSET_DISCONNECTED)
    assert sm.state == State.NO_HEADSET


# --- Callbacks ---

def test_callbacks_fired_on_state_change(sm):
    cb = MagicMock()
    sm.on_state_change(cb)
    sm.set_headset_type(HeadsetType.DECT)
    sm.handle(Event.HEADSET_CONNECTED)
    sm.handle(Event.PTT_PRESS)
    # Should have called cb at least once with TALK
    states_seen = [c.args[0] for c in cb.call_args_list]
    assert State.TALK in states_seen
