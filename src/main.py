# src/main.py
import logging
import signal
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("minihop")

from src.config import Config
from src.state_machine import StateMachine, State, Event, HeadsetType
from src.audio_router import AudioRouter
from src.bluetooth_manager import BluetoothManager
from src.gpio_handler import GpioHandler
from src.led_manager import LedManager
from src.headset_monitor import HeadsetMonitor

CONFIG_PATH = "/home/pi/minihop/config.json"


def main():
    logger.info("MiniHop starting...")
    cfg = Config(CONFIG_PATH)
    sm = StateMachine(cfg)
    router = AudioRouter()
    bt = BluetoothManager()
    gpio = GpioHandler()
    led = LedManager()
    monitor = HeadsetMonitor(cfg, sm)

    # Wire BT manager active device from config
    if cfg.bt_active_mac:
        bt.set_active_device(cfg.bt_active_mac)

    # State machine callbacks → hardware
    def on_state(state: State):
        latched = (cfg.operation_mode == "latch" and state == State.TALK)
        led.update(state, latched=latched)

        if state == State.SWITCHING:
            bt.switch_to_hfp()
        elif state == State.IDLE:
            bt.switch_to_a2dp()
            router.reroute_for_a2dp()
        elif state == State.TALK:
            if sm._headset == HeadsetType.DECT:
                router.reroute_for_dect(talk=True)
            else:
                router.reroute_for_hfp()

    sm.on_state_change(on_state)

    # BlueZ → state machine (single registration handles all BT events)
    bt.on_event(sm.handle)

    # GPIO → state machine
    gpio.on_ptt_press(lambda: sm.handle(Event.PTT_PRESS))
    gpio.on_ptt_release(lambda: sm.handle(Event.PTT_RELEASE))
    gpio.on_mode_change(lambda: (
        setattr(cfg, "operation_mode", _cycle_mode(cfg.operation_mode)),
        cfg.save(),
        sm.handle(Event.MODE_CHANGE)
    ))

    # Start background threads
    bt.start()
    monitor.start()

    logger.info("MiniHop running. Press Ctrl+C to stop.")

    def shutdown(sig, frame):
        logger.info("Shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    while True:
        sm.tick()
        time.sleep(0.1)


def _cycle_mode(current: str) -> str:
    modes = ["dynamic", "latch", "permanent"]
    idx = modes.index(current) if current in modes else 0
    return modes[(idx + 1) % len(modes)]


if __name__ == "__main__":
    main()
