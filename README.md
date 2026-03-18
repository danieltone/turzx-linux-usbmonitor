# TurZX Linux USB Monitor Toolkit

**First proven end-to-end Linux rendering for Turing/UsbMonitor 3.5" USB displays (`1a86:5722`).**

No Windows app required. Color and text rendering with Python on Linux.

---

## Setup & Quick Start

### 1. Install Dependencies

```bash
pip install pyserial Pillow
```

### 2. Display a Color

```bash
python3 turing_color_test.py
```

Cycles through: **red** → **green** → **blue** → **white** → **black** (each held 3s).

### 3. Display Text

```bash
python3 turing_text_test.py "Hello" "World" "Test"
```

Renders each message centered with automatic color rotation, then all three stacked.

---

## What This Project Includes

### Working Scripts (✓ Tested on Linux)
- [turing_color_test.py](turing_color_test.py) — full-screen colors
- [turing_text_test.py](turing_text_test.py) — text rendering with Pillow
- [turing_usb_monitor_test.py](turing_usb_monitor_test.py) — low-level serial test harness

### Reverse-Engineering Artifacts (Educational)
- [REVERSE_ENGINEERING.md](REVERSE_ENGINEERING.md) — full timeline from "no Linux support" to "working"
- [capture_usbmonitor.sh](capture_usbmonitor.sh) — capture USB traffic for analysis
- [extract_frames_from_pcap.py](extract_frames_from_pcap.py) — parse `.pcapng` captures
- [analyze_usbmonitor_serial_calls.py](analyze_usbmonitor_serial_calls.py) — extract metadata from decompiled code
- [logs/](logs/) — captured USB traffic, decompiled IL, test logs

### Infrastructure & Tools
- [summary_live_rates.py](summary_live_rates.py) — monitor USB I/O rates live
- [INSTRUCTIONS.txt](INSTRUCTIONS.txt) — legacy command reference
- [REPO_TOPICS.txt](REPO_TOPICS.txt) — suggested GitHub tags

---

## What Actually Works

The breakthrough:

1. Use **Revision A protocol** (`LcdCommRevA` from open-source [`turing-smart-screen-python`](https://github.com/mathoudebine/turing-smart-screen-python))
2. Call `InitializeComm()` to handshake
3. Call `DisplayPILImage(pillow_image)` to render anything
4. Device reliably updates; no Windows app needed

See [REVERSE_ENGINEERING.md](REVERSE_ENGINEERING.md) for the full journey of how we got here.

---

## Why This Matters

### First Linux Success
This is the **first reproducible, reliable Linux rendering for this exact hardware** without reverse-engineering every detail yourself.

### Educational Value
You get:
- Complete reverse-engineering walkthrough (5 phases: discovery → decompilation → hypothesis testing → breakthrough → validation)
- USB traffic captures and parsing scripts
- .NET decompilation outputs (IL assembly)
- Test infrastructure for serial protocol debugging

### For ESP32/Embedded Users
Reference implementation shows how to drive this display from any platform that can do serial + Python or ported C/Rust.

---

## Project Status

- ✅ Linux communication confirmed and tested
- ✅ Text and color rendering verified on hardware
- ✅ Reproducible, documented workflow
- ✅ Reverse-engineering artifacts included (USB captures, IL decompilation, phase breakdown)
- ⚠️ Some experimental/diagnostic scripts retained for learning (use main three scripts for production)

---

## For Reverse-Engineers & Curious Users

Start with [REVERSE_ENGINEERING.md](REVERSE_ENGINEERING.md):

- **Phase 1:** Device identification via `lsusb`, `dmesg`, USB CDC ACM
- **Phase 2:** Protocol reverse-engineering (USB capture + .NET decompilation)
- **Phase 3:** Hypothesis testing (failed attempts that taught us the traps)
- **Phase 4:** The breakthrough (finding the open-source library)
- **Phase 5:** Validation on real hardware

Includes links to live captures, decompiled code snippets, and extracted command IDs.

---

## Hardware Info

- **Device:** Turing Smart Screen 3.5" / UsbMonitor
- **USB ID:** `1a86:5722`
- **Protocol:** USB CDC ACM serial, 115200 baud
- **Display Resolution:** 480×320 (landscape)
- **Color Depth:** RGB565
- **Status on Linux:** ✅ **Fully supported** (as of this project)

---

## Technologies

- **Language:** Python 3
- **Libraries:** `pyserial`, `Pillow` (PIL)
- **OS Support:** Linux (verified on Kali)
- **Protocol:** Open-source `turing-smart-screen-python` (Revision A)
- **USB:** CDC ACM (standard Linux serial)

---

## Tags

`linux`, `python`, `usb-cdc`, `serial`, `reverse-engineering`, `usbmon`, `turing-smart-screen`, `usbmonitor`, `embedded-display`, `raspberry-pi`

---

## Related Work

- [turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) — upstream multi-platform library
- [Turing Smart Screen](https://www.turzx.com) — official product (Windows-only distribution app)

---

## License

This project is released as-is for educational and reverse-engineering purposes. See [LICENSE](LICENSE) if included.

---

## Next Steps for Users

1. **Get it working:** Follow "Setup & Quick Start" above
2. **Learn how:** Read [REVERSE_ENGINEERING.md](REVERSE_ENGINEERING.md)
3. **Extend it:** Modify `turing_text_test.py` to render custom images, system stats, etc.
4. **Share findings:** Document any new device variants, protocol refinements, or platform ports
