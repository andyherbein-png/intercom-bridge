# MiniHop Hardware Specification

This document outlines the hardware requirements and recommendations for the MiniHop Intercom-to-Wireless Bridge.

## 1. Core Processing (SBC)
### Recommended: Raspberry Pi Zero 2 W
* **CPU:** 64-bit Quad-core ARM Cortex-A53 @ 1GHz
* **RAM:** 512MB LPDDR2
* **Reason:** Lowest cost entry point that supports the 64-bit OS required for stable PipeWire and modern BlueZ stacks.

### Alternative (Pro): Raspberry Pi 4 Model B (2GB)
* **Reason:** Better thermal management and dedicated USB 3.0 buses for lower audio latency.

## 2. Bluetooth Connectivity
Bluetooth stability is the most critical factor for this project.

### The "Pro" Choice: Creative BT-W3 / BT-W5
* **Type:** USB Audio Transceiver (Hardware-level switching)
* **Linux View:** Appears as a standard USB Class Audio device.
* **Advantage:** Bypasses BlueZ profile switching bugs; handles A2DP -> HFP transitions with < 100ms latency.

### The "Developer" Choice: RTL8761B Chipset Dongles
* **Example:** LogiLink BT0048, TP-Link UB500 (Rev 2).
* **Linux View:** Standard HCI Controller via BlueZ.
* **Advantage:** Full control via `src/bluetooth_manager.py` D-Bus code. Excellent driver support in Debian Bookworm.

## 3. Intercom Audio Interface (XLR to Pi)
MiniHop requires an interface to bridge the 5-pin XLR (or 4-wire) intercom system.

### Option A: USB Audio Interface (Easiest)
* **Recommended:** **Behringer U-Control UCA202** or a generic **CMedia CM6206** based card.
* **Setup:** Bridges the Line In/Out of the intercom to the Pi's USB bus.

### Option B: I2S Audio HAT (Lowest Latency)
* **Recommended:** **InnoMaker Raspberry Pi HiFi DAC/ADC HAT**.
* **Setup:** Direct GPIO-to-Audio conversion; bypasses USB bus latency.

## 4. Physical Controls
* **PTT Button:** Any momentary N.O. switch connected to GPIO BCM 26 and Ground.
* **Mode Switch:** Any momentary N.O. switch connected to GPIO BCM 27 and Ground.
* **LEDs:** 
  * Red (Talk): GPIO 17
  * Amber (Status): GPIO 27 (shared or separate)

## 5. Power Requirements
* **Minimum:** 5V / 2.5A via Micro-USB (Pi Zero 2) or USB-C (Pi 4).
* **Note:** Use a high-quality "Official" supply to prevent undervoltage during Bluetooth/WiFi transmission bursts.
