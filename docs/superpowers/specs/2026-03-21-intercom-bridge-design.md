# Intercom-to-Wireless Audio Bridge — Design Specification
**Date:** 2026-03-21
**Status:** Draft v1.0

---

## 1. Product Overview

A compact hardware/software bridge that connects professional intercom systems to wireless headsets (Bluetooth or DECT). Designed for stage managers, camera operators, and keypanel users who need wireless freedom without abandoning their existing intercom infrastructure.

**Target hardware:** Raspberry Pi Zero 2W (primary), Raspberry Pi 4 (future AES67 variant)
**Form factor:** Small project box, USB-C powered (battery or wall wart)
**Single user, single headset at a time**

---

## 2. Hardware Architecture

### 2.1 Audio Interfaces

| Interface | Connector | Signal Level | Direction |
|-----------|-----------|-------------|-----------|
| 5-pin XLR | Female | Mic-level in, headphone-level out | Bidirectional (emulates DT-109 headset to beltpack) |
| 4-wire line-level | 2× XLR (1M + 1F) | Line-level | In + Out |
| USB DECT dongle | USB-A | Digital | Bidirectional |
| Bluetooth | Internal | Digital | Bidirectional |

**Note on 5-pin XLR:** The beltpack controls its own intercom transmission independently. The Pi treats the beltpack as an audio interface only — the PTT button on the beltpack is irrelevant to Pi operation.

### 2.2 Input Protection

- **DC blocking capacitors** on all XLR inputs — blocks phantom power and RTS intercom bus voltage
- **600:600Ω isolation transformers** provide galvanic isolation on all XLR inputs and outputs

### 2.3 Encoders

Two rotary encoders with push buttons (Alps EC11 or Bourns PEC11R):
- 3.3V-compatible — use external 1kΩ–10kΩ pull-ups and RC filter for debounce
- **Do not use KY-040 breakout boards** — they have 5V pull-ups incompatible with RPi GPIO

**Dual-purpose encoder UX:**
- Normal mode: adjust gain (Encoder 1 = input level, Encoder 2 = output level)
- Press either encoder → enter menu (active profile selected by default)
- In menu: Encoder 1 navigates/selects, Encoder 2 adjusts values
- Long-press either encoder → exit menu to normal mode

### 2.4 GPIO Pin Assignments

| Function | GPIO |
|----------|------|
| Mode switch (physical toggle) | GPIO 21 |
| PTT button | TBD |
| Encoder 1 A/B/SW | TBD |
| Encoder 2 A/B/SW | TBD |
| Status LEDs | TBD |

### 2.5 Display

128×64 OLED (SSD1306, I2C) — shows:
- Current profile and mode
- Active headset type and connection status
- Gain levels
- Menu navigation
- Hotspot credentials during pairing window

---

## 3. Operating Modes

### 3.1 Dynamic Mode (Default)

Gate with holdover: audio-activated PTT state machine (see Section 6).

- PTT press → immediately switch to full-duplex (HFP for BT, always-on for DECT)
- Hold time (user-configurable, default 3000ms) keeps 2-way active after PTT release
- Timer resets on each PTT press
- After hold expires → return to listen-only (A2DP for BT)

### 3.2 Permanent 2-Way Mode

HFP/full-duplex locked on until toggled off. Activated via:
- On-device menu
- Web UI

Use case: extended intercom conversation where profile switching latency would be disruptive.

---

## 4. Level Profiles

Four profiles, one per interface/headset combination:

| Profile Key | Interface | Headset |
|-------------|-----------|---------|
| `xlr5_bt` | 5-pin XLR | Bluetooth |
| `xlr5_dect` | 5-pin XLR | DECT |
| `wire4_bt` | 4-wire | Bluetooth |
| `wire4_dect` | 4-wire | DECT |

Each profile stores independent `input_db` and `output_db` values. The active profile is determined automatically by which physical interface is connected and which headset type is active.

---

## 5. Headset Connectivity

### 5.1 Bluetooth

- Profile: A2DP (stereo 48kHz, listen-only) ↔ HFP/mSBC (16kHz, bidirectional)
- PTT latency: ~1.2s (profile switch time)
- Stack: BlueZ 5.x + PipeWire + WirePlumber
- Paired headsets stored in BlueZ persistent device database
- Max stored paired devices: platform default (~7); see paired headset management (Section 5.3)

### 5.2 DECT

- USB dongle (Jabra/EPOS/Yealink recommended)
- Always full-duplex capable — no profile switch needed
- PTT latency: <50ms
- Detection: pyudev USB hotplug events
- Active when dongle is connected; auto-registered as PipeWire node

### 5.3 Paired Headset Management

**Stored pairs** are managed through the on-device menu and web UI.

**Maximum paired devices:** The system enforces a soft limit of 5 stored BT pairings (configurable in config.json). When the limit is reached, pairing a new device requires deleting an existing one first.

**Delete Headset menu flow (on-device):**
```
PAIRED HEADSETS
  ▶ ADD NEW
  ▶ DELETE HEADSET     ← enters sub-menu
    ▶ <Device Name 1>
    ▶ <Device Name 2>
    ▶ ...
    → select device → CONFIRM DELETE? [YES] [NO]
```

**Delete Headset (web UI):**
- Paired Devices list shows each stored device with a delete action (requires confirmation modal before removing)

### 5.4 Headset Hot-Swap Detection

`headset_monitor.py` watches for:
- DECT dongle connect/disconnect (pyudev)
- BT headset connect/disconnect (BlueZ D-Bus events)

On headset change: auto-select active profile, update display, update LED state.

---

## 6. PTT State Machine

### 6.1 Bluetooth Path

```
IDLE (A2DP, listen-only)
  │ PTT pressed
  ▼
SWITCHING (amber LED blinks, OLED shows "SWITCHING...")
  │ HFP profile active (~1.2s)
  ▼
TALK (HFP active, green LED solid)
  │ PTT released → hold timer starts (default 3000ms)
  │ PTT pressed again → timer resets
  ▼
IDLE (A2DP, after hold expires)
```

### 6.2 DECT Path

```
IDLE (full-duplex already available)
  │ PTT pressed
  ▼
TALK (green LED solid — immediate, <50ms)
  │ PTT released → hold timer starts
  │ PTT pressed again → timer resets
  ▼
IDLE (after hold expires)
```

### 6.3 Permanent 2-Way Mode

Both paths skip timers and stay in TALK state until mode is toggled off.

### 6.4 LED State Summary

| State | LED Pattern |
|-------|------------|
| No headset | Red slow blink |
| BT connecting | Amber fast blink |
| BT SWITCHING | Amber slow blink |
| TALK (active) | Green solid |
| IDLE (connected) | Green slow blink |
| Hotspot active | Blue slow blink |
| Error | Red rapid blink |

---

## 7. WiFi Hotspot

Off by default. Enabled via on-device menu or physical button hold (TBD).

**Pairing window:** 5 minutes after enabling, credentials shown on OLED:
```
SSID: IntercomBridge-A1B2
PASS: xxxxxxxx
```

After window closes, hotspot stays active for already-connected clients. New connections blocked after window.

Web UI served at `http://192.168.4.1` over hotspot.

---

## 8. Web UI

### 8.1 Aesthetic

Commodore 64 / PETSCII design language:
- Authentic C64 palette (see c64-design-language skill)
- Background: `#20398D`, border/text: `#6076C5`
- Font: C64 Pro Mono, all-caps, PETSCII symbols
- Phone-first layout (min 36px touch targets)
- Boot header on entry screen with blinking cursor

### 8.2 Screens

**Dashboard**
- Boot header: `**** INTERCOM BRIDGE BASIC V0.1 ****`
- Active profile indicator (A/B/C/D badge)
- Input/output level sliders (read-only display + tap to adjust)
- Headset status (BT device name + RSSI, or DECT connected/disconnected)
- Mode toggle: DYNAMIC ↔ PERMANENT 2-WAY
- Quick-access: BT Pairing, Settings

**BT Pairing**
- Scan + list discovered devices
- Paired devices list with delete action (confirmation required)
- Connect/disconnect controls
- Max paired devices warning when limit reached

**Settings**
- Hold time (ms) with slider
- Sidetone per headset type (enable + level)
- BLE PTT: enable + MAC address
- Hotspot: enable toggle + SSID/password display
- Reset to defaults
- About (firmware version, uptime, IP address)

### 8.3 Easter Egg (Future Task)

About page → "IN HONOR OF OPEN SOURCE DEVELOPERS" (violet, `★` symbols) → simultaneous dual encoder press → secret menu → choose PONG or TETRIS on 128×64 OLED. One encoder per player side in landscape mode. Any audio event (PTT, headset connect) exits game immediately.

---

## 9. Software Architecture

### 9.1 System Stack

```
┌─────────────────────────────────┐
│  Web UI (Flask)                 │
│  On-device Menu (luma.oled)     │
├─────────────────────────────────┤
│  state_machine.py (coordinator) │
├──────────────┬──────────────────┤
│  audio_router│ bluetooth_manager│
│  gpio_handler│ headset_monitor  │
│  ble_ptt     │ hotspot_manager  │
│  display_mgr │ led_manager      │
│  menu        │ config           │
│  aes67_bridge│ games (future)   │
└──────────────┴──────────────────┘
         PipeWire + WirePlumber
              BlueZ 5.x
         Linux kernel / GPIO
```

### 9.2 Module Inventory

| Module | Responsibility |
|--------|---------------|
| `state_machine.py` | Central coordinator; owns gate/holdover logic; fires events to all other modules |
| `audio_router.py` | PipeWire routing via pw-link/pw-metadata; gain control; mic mute |
| `bluetooth_manager.py` | BlueZ D-Bus; A2DP↔HFP switching; connection events |
| `gpio_handler.py` | Mode switch GPIO 21; PTT button; rotary encoders via gpiozero |
| `headset_monitor.py` | USB hotplug (pyudev) for DECT; BT connect/disconnect events |
| `ble_ptt.py` | Optional BLE PTT button via bleak library |
| `display_manager.py` | SSD1306 OLED via luma.oled |
| `led_manager.py` | GPIO LED patterns per state |
| `menu.py` | On-device menu system on OLED |
| `web_server.py` | Flask web UI; REST API for config read/write |
| `hotspot_manager.py` | hostapd + dnsmasq; 5-min pairing window |
| `config.py` | JSON config read/write; single source of truth |
| `aes67_bridge.py` | *Future:* aes67-daemon process management (RPi 4 only) |
| `games.py` | *Future:* Easter egg Pong/Tetris |

### 9.3 config.json Structure

```json
{
  "bt_device_mac": "XX:XX:XX:XX:XX:XX",
  "bt_max_paired_devices": 5,
  "dect_dongle_vid_pid": "auto",
  "operation_mode": "dynamic",
  "hold_time_ms": 3000,
  "profiles": {
    "xlr5_bt":   { "input_db": 20, "output_db": 0 },
    "xlr5_dect": { "input_db": 20, "output_db": 0 },
    "wire4_bt":  { "input_db": 0,  "output_db": 0 },
    "wire4_dect":{ "input_db": 0,  "output_db": 0 }
  },
  "sidetone": {
    "bt_enabled": false,   "bt_level_db": -12,
    "dect_enabled": false, "dect_level_db": -12
  },
  "ble_ptt_enabled": false,
  "ble_ptt_mac": "",
  "hotspot_ssid": "IntercomBridge-A1B2",
  "hotspot_password": "xxxxxxxx",
  "hotspot_pairing_window_s": 300
}
```

---

## 10. AES67 Future Path (RPi 4 Variant)

- Requires Ethernet (not WiFi) for PTP timing accuracy
- Stack: `aes67-daemon` + PipeWire + PTP sync
- RTS AES67 keypanels route directly over network, replacing XLR connections
- Same Python service layer — `aes67_bridge.py` manages aes67-daemon process
- RPi Zero 2W: BT/DECT only; RPi 4: BT/DECT + AES67

---

## 11. Open Questions / Decisions Deferred

| Item | Status |
|------|--------|
| PTT button GPIO pin assignment | TBD |
| Encoder GPIO pin assignments | TBD |
| LED GPIO pin assignments | TBD |
| Physical toggle vs software-only mode switch | TBD (GPIO 21 reserved) |
| BLE PTT device compatibility list | TBD |
| Hotspot enable via physical button hold | TBD |
| PCB/schematic for DC blocking + isolation transformers | Out of scope (hardware phase) |

---

## 12. Out of Scope (v1.0)

- Multi-user / multi-headset
- Dante (virtual sound card or chip integration)
- AES67 on RPi Zero 2W
- Mobile app (web UI over hotspot is the UI)
- Cloud connectivity or remote management
