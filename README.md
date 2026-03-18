# TurZX Linux USB Monitor Toolkit

Linux-first tooling and reverse-engineering notes for Turing/UsbMonitor 3.5" displays over USB CDC (`1a86:5722`).

## What actually did the trick

The successful path was:

1. Identify device class correctly (`/dev/ttyACM0`, USB CDC ACM) and avoid treating it as raw SPI/UART.
2. Stop using guessed command framing and use the known working implementation from `turing-smart-screen-python`.
3. Use **Revision A protocol** (`LcdCommRevA`) for this display family, not Rev B.
4. Run `InitializeComm()` and then `DisplayPILImage(...)` through that library.

### Key breakthrough

- The display was not accepting our hand-crafted write streams reliably.
- Using `library/lcd/lcd_comm_rev_a.py` immediately produced deterministic screen updates on Linux.
- Verified successful color and text rendering with:
  - `turing_color_test.py`
  - `turing_text_test.py`

## Why this matters for Linux users

This project demonstrates a complete Linux-native workflow for this monitor model:

- Device detection and validation (`lsusb`, `dmesg`, `/dev/ttyACM0`)
- Serial traffic testing and logging tools
- USB capture helpers (`usbmon` + extraction)
- Reverse-engineering helpers for vendor app behavior
- Final, repeatable rendering using an open-source Python stack

In this workspace, this is the first end-to-end successful Linux run that moved from startup screen (`PLEASE RUN THE APP`) to reliable color/text rendering.

## Quick start

```bash
cd /home/kali/turzx
python3 -u turing_color_test.py
python3 -u turing_text_test.py "TEST 1" "TEST 2" "TEST 3"
```

If needed:

```bash
git clone --depth=1 https://github.com/mathoudebine/turing-smart-screen-python.git
pip install pyserial Pillow
```

## Main scripts

- `turing_color_test.py` - sends full-screen color sequence using known-good Rev A library path.
- `turing_text_test.py` - renders text messages to the display.
- `turing_usb_monitor_test.py` - serial test harness with logging/batch/summary options.
- `summary_live_rates.py` - live monitor for CSV summaries.
- `capture_usbmonitor.sh` - capture USB traffic (`usbmon`) for this VID/PID.
- `extract_frames_from_pcap.py` - parse captured payloads.

## Suggested repository name

- `turzx-linux-usbmonitor`

Alternative names:
- `turing-usbmonitor-linux-lab`
- `usbmonitor-3p5-linux-toolkit`

## Suggested GitHub topics/tags

- `linux`
- `python`
- `usb-cdc`
- `serial`
- `reverse-engineering`
- `usbmon`
- `turing-smart-screen`
- `usbmonitor`
- `embedded-display`
- `raspberry-pi`

## Project status

- ✅ Linux communication confirmed
- ✅ Linux rendering confirmed (color + text)
- ✅ Reproducible scripts in this repo
- ⚠️ Some low-level experimental scripts remain for protocol research history

## Notes

`tmp_init_frame_test.py` and some frame probe files are retained as historical diagnostics from the reverse-engineering phase.
