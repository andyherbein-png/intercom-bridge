# MiniHop Bill of Materials (BOM)

This BOM lists components for two builds: **The Budget Bridge** (minimal cost) and **The Pro Bridge** (maximum stability/low latency).

## 1. The Budget Bridge (~$45)
Ideal for prototyping and home use.

| Item | Recommendation | Price (Est) | Source |
| :--- | :--- | :--- | :--- |
| **SBC** | Raspberry Pi Zero 2 W | $15.00 | [Adafruit](https://www.adafruit.com/product/5217), [PiShop](https://www.pishop.us/product/raspberry-pi-zero-2-w/) |
| **BT Dongle** | Generic RTL8761B USB Adapter | $9.00 | [Amazon (Example)](https://www.amazon.com/s?k=RTL8761B+bluetooth+dongle) |
| **Audio I/O** | Generic USB Audio Adapter (CMedia) | $8.00 | [Amazon](https://www.amazon.com/s?k=usb+audio+adapter+linux) |
| **Storage** | 16GB MicroSD (Class 10) | $7.00 | Local / Amazon |
| **Power** | 5V 2.5A Micro-USB Supply | $8.00 | [CanaKit](https://www.canakit.com/raspberry-pi-adapter-power-supply.html) |
| **Total** | | **~$47.00** | |

## 2. The Pro Bridge (~$110)
Recommended for professional intercom environments where latency and reconnect reliability are paramount.

| Item | Recommendation | Price (Est) | Source |
| :--- | :--- | :--- | :--- |
| **SBC** | Raspberry Pi 4 Model B (2GB) | $35.00 | [Vilros](https://vilros.com/collections/raspberry-pi-4), [PiShop](https://www.pishop.us/product/raspberry-pi-4-model-b-2gb/) |
| **BT Dongle** | Creative BT-W5 (USB-C) | $39.00 | [Creative.com](https://us.creative.com/p/accessories/creative-bt-w5) |
| **Audio I/O** | Behringer U-Control UCA202 | $25.00 | [Sweetwater](https://www.sweetwater.com/store/detail/UCA202--behringer-u-control-uca202-usb-audio-interface) |
| **Storage** | 32GB SanDisk Extreme MicroSD | $12.00 | Amazon |
| **Total** | | **~$111.00** | |

## 3. Peripheral Hardware (Common)
*   **PTT Button:** [16mm Momentary Push Button](https://www.adafruit.com/product/1445) ($2.00)
*   **Mode Switch:** [6mm Tactile Switch](https://www.adafruit.com/product/367) ($1.00/10pk)
*   **Enclosure:** [Official Pi Zero Case](https://www.pishop.us/product/official-raspberry-pi-zero-case/) ($5.00) or 3D Printed.

## 4. Hardware Selection Notes
*   **BT-W5 Advantage:** This dongle appears as a standard USB Sound Card. It handles codec switching (aptX-LL) in hardware, meaning the Pi doesn't have to manage complex D-Bus profiles. It is the single best stability upgrade for this project.
*   **RTL8761B Advantage:** Best-in-class Linux driver support for standard HCI mode. Use this if you want to use the software-based `BluetoothManager` for fine-grained control over which device is connected.
