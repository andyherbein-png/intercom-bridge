# intercom-bridge (MiniHop)

> **Vision:** A professional-grade bridge between traditional wired intercom systems (5-pin XLR / 4-wire) and the wireless freedom of Bluetooth (HFP/A2DP) and DECT headsets.

Built for the Raspberry Pi, `intercom-bridge` (code-named **MiniHop**) provides a low-latency, software-defined audio engine that manages the complex handshakes required for seamless push-to-talk (PTT) communication.

## 🚀 Key Features

- **Multi-Mode PTT State Machine:** 
  - `Dynamic`: Classic hold-to-talk with a configurable hold-timer (gate) to prevent syllable clipping.
  - `Latch`: Toggle talk state with a single press.
  - `Permanent`: Open mic for always-on environments.
- **Smart Bluetooth Routing:** Automatically switches between high-quality A2DP (listening) and low-latency HFP (talking) when PTT is engaged.
- **DECT Support:** Full integration for high-range wireless headsets (Jabra, EPOS, etc.).
- **Visionary UI:** A C64-themed mobile-responsive dashboard for real-time status, mode selection, and level monitoring.
- **Easter Egg:** A built-in Chess AI (accessible via the dashboard) for those quiet moments on set.

## 🛠 Tech Stack

- **Audio Engine:** PipeWire (via `pw-link` and `pw-metadata`) for ultra-low latency routing.
- **State Logic:** Event-driven Python state machine with sub-100ms response times.
- **Hardware Interface:** `gpiozero` for physical PTT/Mode buttons and LED feedback.
- **Web UI:** Flask + SSE (Server-Sent Events) for real-time telemetry.

## 📦 Installation

```bash
git clone https://github.com/andyherbein-png/intercom-bridge.git
cd intercom-bridge
./setup.sh
```

## 🧪 Testing

The project includes an exhaustive test suite (51+ tests) with full hardware emulation for developing on non-Pi hardware (macOS/Linux).

```bash
./venv/bin/pytest
```

---

*“Bridging the gap between the wire and the air with style.”*
