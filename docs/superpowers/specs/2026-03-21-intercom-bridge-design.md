# MiniHop — Intercom-to-Wireless Audio Bridge Design Specification
**Date:** 2026-03-21
**Status:** Draft v1.2

---

## 1. Product Overview

**MiniHop** is a compact hardware/software bridge that connects professional intercom systems to wireless headsets (Bluetooth or DECT). Designed for stage managers, camera operators, and keypanel users who need wireless freedom without abandoning their existing intercom infrastructure.

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

Three modes are available, selectable via on-device menu or web UI. Stored in `config.json` as `operation_mode`.

### 3.1 Dynamic Mode (Default) — `"dynamic"`

Button-triggered gate with holdover. The term "gate" describes the hold-timer behavior: the 2-way path stays open (held) for a configurable duration after PTT is released, preventing rapid profile churn during conversation. There is no audio-level detection — PTT button press is the only trigger.

- PTT press → immediately switch to full-duplex (HFP for BT, always-on for DECT)
- Hold time (user-configurable, default 3000ms) keeps 2-way active after PTT release
- Timer resets on each PTT press while in TALK state
- After hold expires → return to listen-only (A2DP for BT)

### 3.2 Latch Talk Mode — `"latch"`

Toggle-style PTT. First press engages talk; second press disengages. No hold timer.

- PTT press (first) → engage full-duplex, green LED solid, OLED shows `LATCHED`
- PTT press (second) → disengage, return to listen-only
- Designed for keypanel users who use the panel's own talk keys to control channel selection — MiniHop mirrors that state on the wireless side

**Keypanel use case:** When connected to a keypanel (4-wire or 5-pin XLR), the user activates a talk key on the panel to speak to a channel. They press MiniHop's PTT once to latch wireless talk on for that conversation, then press again when done. This avoids holding a button while also working the keypanel.

**BT note:** For BT, latch mode keeps HFP engaged for the duration of the latched session (no A2DP reversion between key presses).

### 3.3 Permanent 2-Way Mode — `"permanent"`

HFP/full-duplex locked on until toggled off. Activated via:
- On-device menu
- Web UI

Use case: extended intercom conversation where any interruption in the mic path would be disruptive.

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
- Pairing inventory is stored in BlueZ's persistent device database (authoritative source)
- `bt_active_mac` in config.json tracks the currently preferred/connected device
- Max stored pairings: soft limit of 5 (configurable via `bt_max_paired_devices`)

### 5.2 DECT

- USB dongle (Jabra/EPOS/Yealink — compatibility to be confirmed during hardware phase)
- Always full-duplex capable — no profile switch needed
- PTT latency: <50ms
- Detection: pyudev USB hotplug events
- Active when dongle is connected; auto-registered as PipeWire node
- **DECT IDLE audio:** intercom audio (XLR in) routes to headset speaker (listen-only). Mic path is closed until PTT press, identical behavior to BT A2DP IDLE.

### 5.3 BLE PTT (Optional, v1.0)

Optional third-party BLE button as a wireless PTT trigger. When enabled, the BLE device is paired once and its MAC stored in config. It connects as a BLE peripheral; the device must support a button characteristic readable via GATT notify (HID or custom). On button-down event, `ble_ptt.py` fires a PTT_PRESS event into `state_machine.py`; on button-up, PTT_RELEASE. Integrates identically to the physical PTT button from the state machine's perspective.

### 5.4 Sidetone

Sidetone routes a portion of the user's own mic signal back to the headset speaker for natural speech feel. Configurable independently per headset type.

- **BT sidetone:** applied via PipeWire loopback within the HFP audio graph. Headset-dependent — some BT headsets apply their own sidetone hardware-side; if so, software sidetone should be disabled to avoid doubling. Default: off.
- **DECT sidetone:** applied via PipeWire loopback within the DECT audio graph. Default: off.
- Level configurable in dB. Sidetone is only active in TALK state; muted in IDLE.

### 5.5 Paired Headset Management

**Stored pairs** are managed through the on-device menu and web UI.

**Maximum paired devices:** The system enforces a soft limit (default 5, configurable via `bt_max_paired_devices`). When the limit is reached, the ADD NEW option is replaced with a message: `MAX DEVICES REACHED — DELETE ONE FIRST`.

**Delete Headset menu flow (on-device):**
```
PAIRED HEADSETS
  ▶ ADD NEW
  ▶ DELETE HEADSET     ← enters sub-menu
    ▶ <Device Name 1>  ← [ACTIVE] tag shown if currently connected
    ▶ <Device Name 2>
    ▶ ...
    → select device
    → if active: CONFIRM? DEVICE IS ACTIVE. DISCONNECT AND DELETE? [YES] [NO]
    → if inactive: CONFIRM DELETE? [YES] [NO]
```

**Edge cases:**
- **Deleting the active headset:** Permitted. User sees extra warning "DEVICE IS ACTIVE". On YES: graceful BT disconnect → state_machine transitions to NO HEADSET state → BlueZ unpair. Audio path returns to IDLE/disconnected immediately.
- **Deleting the last paired device:** Permitted. User sees warning "NO HEADSET WILL REMAIN PAIRED". On YES: device is removed, system enters NO HEADSET state. User must pair a new device to restore audio.
- **Deleting while in SWITCHING state (BT):** Delete is blocked during SWITCHING. Menu shows `CANNOT DELETE — SWITCHING IN PROGRESS`.

**Delete Headset (web UI):**
- Paired Devices list shows each device with name, MAC, and connected status
- Active device shown with a status badge
- Delete button opens confirmation modal: standard text, or "DEVICE IS ACTIVE — THIS WILL DISCONNECT YOUR HEADSET" if active
- Last device: modal adds "NO HEADSET WILL REMAIN PAIRED"

### 5.6 Headset Hot-Swap Detection

`headset_monitor.py` watches for:
- DECT dongle connect/disconnect (pyudev)
- BT headset connect/disconnect (BlueZ D-Bus events)

On headset change: auto-select active profile, update display, update LED state.

---

## 6. PTT State Machine

### 6.1 Bluetooth Path

```
IDLE (A2DP, listen-only — XLR in → headset speaker only, mic closed)
  │ PTT pressed
  ▼
SWITCHING (amber LED blinks, OLED shows "SWITCHING...")
  │ HFP profile negotiated (~1.2s)
  ▼
TALK (HFP active, green LED solid — XLR in ↔ headset, mic open)
  │ PTT released → hold timer starts (default 3000ms)
  │ PTT pressed again → timer resets, stay in TALK
  ▼
IDLE (A2DP, after hold expires)
```

**SWITCHING edge cases:**
- **PTT released during SWITCHING:** Profile switch continues to completion. On HFP active, hold timer starts immediately from TALK state (behaves as if PTT was held to TALK then released). Does not abort back to IDLE.
- **PTT pressed again during SWITCHING:** Ignored (already switching). No queuing needed — hold timer will start from TALK, and a new press there resets the timer normally.
- **Headset disconnects during SWITCHING:** Abort to NO HEADSET state; emit disconnect event to display and LED managers.

### 6.2 DECT Path

```
IDLE (full-duplex available, XLR in → headset speaker only, mic closed)
  │ PTT pressed
  ▼
TALK (mic opens — immediate, <50ms, green LED solid)
  │ PTT released → hold timer starts
  │ PTT pressed again → timer resets, stay in TALK
  ▼
IDLE (mic closes, after hold expires)
```

### 6.3 Latch Talk Mode

```
IDLE (listen-only)
  │ PTT pressed (first press)
  ▼
TALK (mic open, green LED solid, OLED shows "LATCHED")
  │ PTT pressed (second press)
  ▼
IDLE (listen-only)
```

No hold timer. BT stays in HFP for the full latched session.

### 6.4 Permanent 2-Way Mode

Both paths stay in TALK state (mic open) indefinitely until the mode is toggled off via menu or web UI. Hold timer is not started on PTT release.

### 6.4 Profile-Switch Coordination (BT)

The A2DP→HFP transition is a joint operation between `bluetooth_manager.py` and `audio_router.py`, orchestrated by `state_machine.py`:

1. `state_machine` receives PTT_PRESS → enters SWITCHING state
2. `state_machine` calls `bluetooth_manager.switch_to_hfp()`
3. BlueZ negotiates HFP; `bluetooth_manager` fires `HFP_ACTIVE` event when complete
4. `state_machine` receives `HFP_ACTIVE` → calls `audio_router.reroute_for_hfp()`
5. `audio_router` re-links PipeWire nodes for HFP graph (mic + speaker)
6. `state_machine` enters TALK state, starts hold timer on PTT release

Reverse (TALK → IDLE): `state_machine` calls `audio_router.reroute_for_a2dp()` then `bluetooth_manager.switch_to_a2dp()`.

### 6.5 LED State Summary (updated for latch)

| State | LED Pattern |
|-------|------------|
| No headset | Red slow blink |
| BT connecting | Amber fast blink |
| BT SWITCHING | Amber slow blink |
| TALK — dynamic/holdover | Green solid |
| TALK — latched | Green fast blink (distinguishes latch from permanent) |
| TALK — permanent | Green solid |
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

After the 5-minute window closes:
- Hotspot remains active for already-connected clients
- New connections are blocked (hostapd MAC whitelist updated)
- Existing browser sessions remain fully functional with no timeout — the user's web UI session continues until they close it or the device powers off

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
- Mode selector: DYNAMIC / LATCH / PERMANENT 2-WAY (3-way toggle)
- Quick-access: BT Pairing, Settings

**BT Pairing**
- Scan + list discovered devices
- Paired devices list: name, MAC, connected status, delete button
- Connect/disconnect controls
- Warning banner when `bt_max_paired_devices` limit reached
- Delete confirmation modal (with active-device and last-device warnings as applicable)

**Settings**
- Hold time (ms) with slider
- Sidetone per headset type (enable toggle + level slider)
- BLE PTT: enable toggle + MAC address field
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
| `state_machine.py` | Central coordinator; owns gate/holdover logic; orchestrates profile-switch handoff between audio_router and bluetooth_manager |
| `audio_router.py` | PipeWire routing via pw-link/pw-metadata; gain control; mic mute; sidetone loopback |
| `bluetooth_manager.py` | BlueZ D-Bus; A2DP↔HFP switching; connection/pairing events; fires HFP_ACTIVE / A2DP_ACTIVE events |
| `gpio_handler.py` | Mode switch GPIO 21; PTT button; rotary encoders via gpiozero |
| `headset_monitor.py` | USB hotplug (pyudev) for DECT; BT connect/disconnect events |
| `ble_ptt.py` | Optional BLE PTT button via bleak library; fires PTT_PRESS/PTT_RELEASE to state_machine |
| `display_manager.py` | SSD1306 OLED via luma.oled |
| `led_manager.py` | GPIO LED patterns per state |
| `menu.py` | On-device menu system on OLED |
| `web_server.py` | Flask web UI; REST API for config read/write |
| `hotspot_manager.py` | hostapd + dnsmasq; 5-min pairing window; MAC whitelist management |
| `config.py` | JSON config read/write; single source of truth |
| `aes67_bridge.py` | *Future:* aes67-daemon process management (RPi 4 only) |
| `games.py` | *Future:* Easter egg Pong/Tetris |

### 9.3 Process Supervision

All modules run as a single Python process managed by a **systemd unit file** (`intercom-bridge.service`). systemd handles:
- Auto-start on boot
- Restart on crash (RestartSec=3s)
- Journal logging (`journalctl -u intercom-bridge`)

### 9.4 config.json Structure

```json
{
  "config_version": 1,
  "bt_active_mac": "XX:XX:XX:XX:XX:XX",
  "bt_max_paired_devices": 5,
  "dect_dongle_vid_pid": "auto",
  "operation_mode": "dynamic",   // "dynamic" | "latch" | "permanent"
  "hold_time_ms": 3000,           // only applies in dynamic mode
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

**Notes:**
- `bt_active_mac`: the currently preferred/connected BT device. Full pairing inventory is stored in BlueZ; this is not a list.
- `config_version`: enables migration logic if the schema changes in future versions.

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
| Hotspot enable via physical button hold | TBD |
| BLE PTT device type confirmation (HID vs custom GATT) | TBD — to confirm with test device |
| DECT dongle compatibility (Jabra/EPOS/Yealink) | TBD — to confirm during hardware phase |
| PCB/schematic for DC blocking + isolation transformers | Out of scope (hardware phase) |
| Power budget (USB-C supply rating for Zero 2W + BT + OLED + DECT) | TBD — estimate during hardware phase |

---

## 12. Out of Scope (v1.0)

- Multi-user / multi-headset
- Dante (virtual sound card or chip integration)
- AES67 on RPi Zero 2W
- Mobile app (web UI over hotspot is the UI)
- Cloud connectivity or remote management
- Audio-level-triggered (voice-activity) PTT — button only
