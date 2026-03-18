# Reverse-Engineering the Turing UsbMonitor 3.5" on Linux

## Overview

This document traces the journey of discovering how to reliably render content on a Turing/UsbMonitor 3.5" USB display (`1a86:5722`) from pure Linux, without the Windows GUI.

## Key Breakthrough

After reverse-engineering the Windows vendor application using IL decompilation and USB traffic analysis, we discovered:

- **Device is Revision A** (`LcdCommRevA`), not Revision B
- **Correct command** is `0xC5` (197 decimal) for `DISPLAY_BITMAP`, not `0xC6`
- **Protocol uses 10-byte framed packets** (not raw 6-byte headers we were guessing)
- **Working reference implementation exists** in `turing-smart-screen-python` library

This breakthrough allows reliable, deterministic display rendering from Linux with 3-5 lines of Python.

---

## Phase 1: Device Identification (Learning what we're working with)

### Files
- `lsusb` output: identified `1a86:5722` as USB vendor `QinHeng Electronics`
- `dmesg`: saw CDC ACM enumeration as `/dev/ttyACM0`

### Finding
Device is **USB CDC ACM serial port**, not raw SPI/UART or HID. Communicates via 115200 baud serial protocol.

### Lessons Learned
- Do not assume display protocols are raw memory-mapped or use standard graphics-bus framing
- USB CDC ACM = serial device = you need to know the command protocol

---

## Phase 2: Protocol Reverse-Engineering (Discovering the command bytes)

### Approach
1. Captured live USB traffic using `usbmon` while Windows app ran
2. Extracted raw frame payloads using `extract_frames_from_pcap.py`
3. Decompiled Windows EXE (`UsbMonitor.exe`) using Mono/.NET tools

### Tools Used
- **Capture**: `usbmon` kernel module + `tshark`
- **Extraction**: [extract_frames_from_pcap.py](extract_frames_from_pcap.py) (iteratively fixed payload parsing)
- **Decompilation**: 
  - ILSpy CLI for IL assembly extraction
  - Custom Python scripts to parse IL metadata and identify command IDs

### Key Discoveries (from IL decompilation)
- Command `102` = CLEAR / hardware reset
- Command `109` = SCREEN_ON / wake
- Command `197` = DISPLAY_BITMAP / frame data
- Commands use 6-byte header format initially guessed (packed coordinates + command)

### Captured Examples
- [frames_probe.txt](frames_probe.txt): sample hex payloads from live capture
- [logs/ilspy/](logs/ilspy/): decompiled IL code for UsbMonitor.exe
- [logs/usbmonitor_serial_calls.txt](logs/usbmonitor_serial_calls.txt): discovered serial write methods

### Lessons Learned
- Obfuscated .NET binaries are still reversible with IL decompilation
- USB traffic capture works but requires understanding `usbmon` field parsing (`usbcom.data.out_payload`)
- Not all captured packets end up successfully rendering (some are init/handshake only)

---

## Phase 3: Hypothesis Testing (Guessing command frames)

### Failed Attempts
1. **Guessed 6-byte header framing** → sent `[x0_packed, y0_packed, x1_packed, y1_packed, cmd]`
   - Result: device sometimes went all-white and stuck
   - Lesson: without precise framing and full protocol spec, raw sends cause undefined behavior

2. **Sent init commands (102, 109) once, then streamed frames**
   - Result: screen cleared to white on init, but frame data was ignored
   - Lesson: init commands reset/clear, frame must come after or have its own init

3. **Tried multiple command modes** (`194`, `197`, `198`) with various payloads
   - Result: inconsistent rendering or no change at all
   - Lesson: command ID selection matters; wrong command = device silently ignores or clears

4. **Hand-crafted RGB565 byte ordering** (little-endian vs big-endian guessing)
   - Result: only white displayed reliably; red/green/blue were wrong or absent
   - Lesson: without a known-good reference, byte order is a guess; led to days of debugging

### Key Realization
- Device has its own firmware and protocol state machine
- Guessed protocol != actual protocol
- Need to find or derive the exact framing (10-byte packets, command at head + tail)

---

## Phase 4: The Breakthrough (Finding turing-smart-screen-python)

### Discovery Method
Searched GitHub for open-source projects targeting this exact VID:PID combination.

### Found
[mathoudebine/turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python): complete reverse-engineered Python library with support for multiple Turing display revisions.

### Key Module
[library/lcd/lcd_comm_rev_a.py](https://github.com/mathoudebine/turing-smart-screen-python/blob/main/library/lcd/lcd_comm_rev_a.py):
- Implements correct 10-byte framing: `[cmd, 8-byte payload, cmd]`
- Exports `LcdCommRevA` class for rev-A devices
- `DisplayPILImage()` handles PIL → RGB565 → serial writes automatically
- Includes init sequence, orientation setting, brightness control

### Result
One call to `lcd.DisplayPILImage(image)` → deterministic, reliable rendering.

### Lessons Learned
- **Search for existing solutions first.** Reverse-engineering from scratch is education; using battle-tested code is engineering.
- Even if specs aren't public, communities often solve these problems independently
- Open-source enables reproducibility on unsupported platforms (Linux)

---

## Phase 5: Validation on Linux (Proving it works)

### Test Scripts
1. [turing_color_test.py](turing_color_test.py)
   - Sends solid red, green, blue, white, black frames
   - Each held for 3 seconds
   - Result: **all 5 colors displayed correctly and sequentially** ✓

2. [turing_text_test.py](turing_text_test.py)
   - Renders Python Pillow text overlays
   - Three custom messages, each in different color / background
   - Result: **text displays with correct fonts, positioning, and colors** ✓

### Verification
- Device no longer shows "PLEASE RUN THE APP" after `InitializeComm()`
- Screen reliably updates on every new `DisplayPILImage()` call
- No power cycles needed once correct protocol used

---

## What Not To Do (Lessons for Others)

1. **Do not guess command framing** without a reference. Leads to device getting into undefined states.
2. **Do not assume byte order.** RGB565 big-endian ≠ little-endian; test both or find spec.
3. **Do not ignore init/handshake sequences.** Device firmware may require specific startup.
4. **Do not send all data in one write.** Buffer the device; chunk frames with delays.
5. **Do not ignore existing open-source projects.** Even if unmaintained, they're a reference.

---

## Artifacts and Evidence

### USB Captures
- [logs/usbcap_active.pcapng](logs/usbcap_active.pcapng): raw `usbmon` capture during Windows app operation

### Decompilation Outputs
- [logs/ilspy/](logs/ilspy/): IL assembly dump from `ILSpy` CLI
- [logs/usbmonitor_serial_calls.txt](logs/usbmonitor_serial_calls.txt): extracted metadata about serial writes
- [logs/type_who.cs](logs/type_who.cs): decompiled C# method signatures

### Frame Extractions
- [frames_probe.txt](frames_probe.txt): sample raw hex frames from captures

### Test & Logging Infrastructure
- [turing_usb_monitor_test.py](turing_usb_monitor_test.py): interactive serial tester with batch/logging modes
- [summary_live_rates.py](summary_live_rates.py): live monitor for USB traffic summaries
- [logs/](logs/): runtime logs, live summaries, frame dumps

---

## Recommended Reading Order

1. **Start here:** [README.md](README.md) — quick start and project overview
2. **Learn how to reproduce:** "Setup & Quick Start" section in [README.md](README.md)
3. **Understand the journey:** This document (you are here)
4. **Dive into code:** [turing_color_test.py](turing_color_test.py) and [turing_text_test.py](turing_text_test.py)
5. **Explore internals:** [turing_usb_monitor_test.py](turing_usb_monitor_test.py) for low-level serial testing

---

## Key Takeaway

Linux support for this display **exists and works reliably** when using the correct protocol implementation. The Windows-only era for this device is over.
