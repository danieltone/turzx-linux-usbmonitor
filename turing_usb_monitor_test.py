#!/usr/bin/env python3
import argparse
import datetime as dt
import os
import sys
import threading
import time

import serial


def timestamp() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def format_timestamp(mode: str, start_time: float) -> str:
    if mode == "epoch":
        return f"{time.time():.3f}"
    if mode == "elapsed":
        return f"+{(time.time() - start_time):.3f}s"
    return timestamp()


def default_log_path(base_dir: str) -> str:
    os.makedirs(base_dir, exist_ok=True)
    name = dt.datetime.now().strftime("turing_usb_%Y%m%d_%H%M%S.log")
    return os.path.join(base_dir, name)


def to_hex(data: bytes) -> str:
    return data.hex(" ") if data else ""


def parse_frame_line(line: str) -> str:
    cleaned = line.split("#", 1)[0].strip()
    return cleaned


def read_frames_file(path: str) -> list[tuple[int, str]]:
    frames: list[tuple[int, str]] = []
    with open(path, "r", encoding="utf-8") as file:
        for index, raw in enumerate(file, start=1):
            frame = parse_frame_line(raw)
            if not frame:
                continue
            frames.append((index, frame))
    return frames


def dated_csv_path(base_path: str, epoch_seconds: float) -> str:
    date_suffix = dt.datetime.fromtimestamp(epoch_seconds).strftime("%Y%m%d")
    stem, ext = os.path.splitext(base_path)
    ext = ext or ".csv"
    return f"{stem}_{date_suffix}{ext}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="USB CDC test tool for Turing UsbMonitor devices"
    )
    parser.add_argument("--port", default="/dev/ttyACM0", help="Serial device path")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (API-required for CDC)")
    parser.add_argument(
        "--logfile",
        default=None,
        help="Path to log file (default: ./logs/turing_usb_YYYYmmdd_HHMMSS.log)",
    )
    parser.add_argument("--read-size", type=int, default=256, help="Bytes per read")
    parser.add_argument("--read-delay", type=float, default=0.01, help="Reader loop delay seconds")
    parser.add_argument(
        "--send",
        default=None,
        help="One-shot mode: hex payload to send once and exit (example: '01 02 aa 55')",
    )
    parser.add_argument(
        "--send-file",
        default=None,
        help="Batch mode: path to text file with one hex frame per line",
    )
    parser.add_argument(
        "--rx-time",
        type=float,
        default=1.0,
        help="One-shot/batch mode: seconds to keep reading responses after each send",
    )
    parser.add_argument(
        "--frame-delay",
        type=float,
        default=0.2,
        help="Batch mode: delay in seconds between frames",
    )
    parser.add_argument(
        "--loop",
        type=int,
        default=1,
        help="Batch mode: number of times to repeat --send-file (0 = infinite)",
    )
    parser.add_argument(
        "--timestamp-prefix",
        choices=["wall", "epoch", "elapsed"],
        default="wall",
        help="Timestamp style for log prefix: wall (default), epoch, or elapsed",
    )
    parser.add_argument(
        "--quiet-rx",
        action="store_true",
        help="Do not print RX lines to console (still writes RX to log file)",
    )
    parser.add_argument(
        "--quiet-tx",
        action="store_true",
        help="Do not print TX/loop lines to console (still writes TX/loop to log file)",
    )
    parser.add_argument(
        "--summary-every",
        type=float,
        default=0.0,
        help="Print periodic summary every N seconds (0 disables)",
    )
    parser.add_argument(
        "--summary-csv",
        default=None,
        help="Optional CSV file path for periodic/final summary rows",
    )
    parser.add_argument(
        "--summary-csv-daily",
        action="store_true",
        help="When used with --summary-csv, rotate to date-suffixed CSV files (one per day)",
    )
    args = parser.parse_args()

    if args.send is not None and args.send_file is not None:
        print("ERROR: Use either --send or --send-file, not both.")
        return 2

    if args.summary_every < 0:
        print("ERROR: --summary-every must be >= 0")
        return 2

    if args.summary_csv_daily and args.summary_csv is None:
        print("ERROR: --summary-csv-daily requires --summary-csv")
        return 2

    log_path = args.logfile or default_log_path("logs")
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)

    try:
        ser = serial.Serial(args.port, args.baud, timeout=0.1)
    except Exception as exc:
        print(f"ERROR: Could not open {args.port}: {exc}")
        return 1

    stop_event = threading.Event()
    write_lock = threading.Lock()

    with open(log_path, "a", encoding="utf-8") as log:
        run_start = time.time()
        stats_lock = threading.Lock()
        tx_frames = 0
        tx_bytes = 0
        rx_packets = 0
        rx_bytes = 0
        last_summary_time = run_start

        if args.summary_csv is not None:
            csv_dir = os.path.dirname(args.summary_csv)
            if csv_dir:
                os.makedirs(csv_dir, exist_ok=True)

        def stamp() -> str:
            return format_timestamp(args.timestamp_prefix, run_start)

        def log_line(line: str) -> None:
            with write_lock:
                log.write(line + "\n")
                log.flush()

        def add_tx_stats(payload_len: int) -> None:
            nonlocal tx_frames, tx_bytes
            with stats_lock:
                tx_frames += 1
                tx_bytes += payload_len

        def add_rx_stats(packet_len: int) -> None:
            nonlocal rx_packets, rx_bytes
            with stats_lock:
                rx_packets += 1
                rx_bytes += packet_len

        def emit_summary(force: bool = False) -> None:
            nonlocal last_summary_time
            if args.summary_every <= 0 and not force:
                return
            if args.summary_every <= 0 and force and args.summary_csv is None:
                return

            now = time.time()
            if not force and (now - last_summary_time) < args.summary_every:
                return

            with stats_lock:
                summary = (
                    f"[{stamp()}] SUMMARY tx_frames={tx_frames} tx_bytes={tx_bytes} "
                    f"rx_packets={rx_packets} rx_bytes={rx_bytes}"
                )
            print(summary)
            log_line(summary)
            if args.summary_csv is not None:
                elapsed = now - run_start
                kind = "final" if force else "periodic"
                csv_path = (
                    dated_csv_path(args.summary_csv, now)
                    if args.summary_csv_daily
                    else args.summary_csv
                )
                csv_needs_header = (not os.path.exists(csv_path)) or (os.path.getsize(csv_path) == 0)
                with open(csv_path, "a", encoding="utf-8") as csv_file:
                    if csv_needs_header:
                        csv_file.write(
                            "timestamp,epoch,elapsed_s,kind,tx_frames,tx_bytes,rx_packets,rx_bytes\n"
                        )
                    csv_file.write(
                        f"{stamp()},{now:.3f},{elapsed:.3f},{kind},{tx_frames},{tx_bytes},{rx_packets},{rx_bytes}\n"
                    )
            last_summary_time = now

        print(f"Opened {args.port} @ {args.baud}")
        print(f"Logging to: {log_path}")
        if args.send is None and args.send_file is None:
            print("Type hex bytes to send (example: 01 02 aa 55), or 'quit' to exit.")
        else:
            print("Batch/one-shot mode active: terminal input is ignored.")

        log_line(
            f"[{stamp()}] OPEN port={args.port} baud={args.baud} ts_mode={args.timestamp_prefix}"
        )

        if args.send is not None or args.send_file is not None:
            if args.send is not None:
                frames: list[tuple[int, str]] = [(0, args.send)]
            else:
                try:
                    frames = read_frames_file(args.send_file)
                except Exception as exc:
                    print(f"ERROR: Could not read --send-file {args.send_file}: {exc}")
                    log_line(f"[{stamp()}] ERROR cannot read --send-file {args.send_file}: {exc}")
                    try:
                        ser.close()
                    except Exception:
                        pass
                    log_line(f"[{stamp()}] CLOSE")
                    return 2

                if not frames:
                    print("ERROR: --send-file has no valid frames.")
                    log_line(f"[{stamp()}] ERROR empty or invalid --send-file: {args.send_file}")
                    try:
                        ser.close()
                    except Exception:
                        pass
                    log_line(f"[{stamp()}] CLOSE")
                    return 2

                if args.loop < 0:
                    print("ERROR: --loop must be >= 0")
                    log_line(f"[{stamp()}] ERROR invalid --loop value: {args.loop}")
                    try:
                        ser.close()
                    except Exception:
                        pass
                    log_line(f"[{stamp()}] CLOSE")
                    return 2

            if args.send_file is not None:
                total_loops = args.loop
                loop_counter = 0
                infinite = total_loops == 0
            else:
                total_loops = 1
                loop_counter = 0
                infinite = False

            while infinite or loop_counter < total_loops:
                loop_counter += 1
                if args.send_file is not None:
                    if infinite:
                        loop_msg = f"[{stamp()}] LOOP {loop_counter} (infinite mode)"
                    else:
                        loop_msg = f"[{stamp()}] LOOP {loop_counter}/{total_loops}"
                    if not args.quiet_tx:
                        print(loop_msg)
                    log_line(loop_msg)

                for index, frame_text in frames:
                    try:
                        payload = bytes.fromhex(frame_text)
                    except ValueError:
                        if args.send is not None:
                            print("ERROR: Invalid hex for --send. Example: --send '01 02 aa 55'")
                            log_line(f"[{stamp()}] ERROR invalid --send payload: {args.send}")
                        else:
                            print(f"ERROR: Invalid hex on --send-file line {index}: {frame_text}")
                            log_line(
                                f"[{stamp()}] ERROR invalid --send-file line {index}: {frame_text}"
                            )
                        try:
                            ser.close()
                        except Exception:
                            pass
                        log_line(f"[{stamp()}] CLOSE")
                        return 2

                    try:
                        ser.write(payload)
                        ser.flush()
                    except Exception as exc:
                        msg = f"[{stamp()}] ERROR TX: {exc}"
                        print(msg)
                        log_line(msg)
                        try:
                            ser.close()
                        except Exception:
                            pass
                        log_line(f"[{stamp()}] CLOSE")
                        return 3

                    if args.send is not None:
                        tx_msg = f"[{stamp()}] TX {len(payload)} bytes: {to_hex(payload)}"
                    else:
                        tx_msg = (
                            f"[{stamp()}] TX line {index} {len(payload)} bytes: {to_hex(payload)}"
                        )
                    if not args.quiet_tx:
                        print(tx_msg)
                    log_line(tx_msg)
                    add_tx_stats(len(payload))
                    emit_summary()

                    end_time = time.time() + max(0.0, args.rx_time)
                    while time.time() < end_time:
                        try:
                            data = ser.read(args.read_size)
                        except Exception as exc:
                            msg = f"[{stamp()}] ERROR RX: {exc}"
                            print(msg)
                            log_line(msg)
                            break

                        if data:
                            rx_msg = f"[{stamp()}] RX {len(data)} bytes: {to_hex(data)}"
                            if not args.quiet_rx:
                                print(rx_msg)
                            log_line(rx_msg)
                            add_rx_stats(len(data))
                            emit_summary()

                        time.sleep(args.read_delay)

                    if args.send_file is not None:
                        time.sleep(max(0.0, args.frame_delay))

                if args.send is not None:
                    break

                if not infinite and loop_counter >= total_loops:
                    break

            try:
                emit_summary(force=True)
                ser.close()
            except Exception:
                pass
            log_line(f"[{stamp()}] CLOSE")
            print("Closed.")
            return 0

        def reader() -> None:
            while not stop_event.is_set():
                try:
                    data = ser.read(args.read_size)
                except Exception as exc:
                    msg = f"[{stamp()}] ERROR RX: {exc}"
                    print(msg)
                    log_line(msg)
                    stop_event.set()
                    return

                if data:
                    msg = f"[{stamp()}] RX {len(data)} bytes: {to_hex(data)}"
                    if not args.quiet_rx:
                        print(msg)
                    log_line(msg)
                    add_rx_stats(len(data))
                emit_summary()

                time.sleep(args.read_delay)

        thread = threading.Thread(target=reader, daemon=True)
        thread.start()

        try:
            while not stop_event.is_set():
                try:
                    line = input("TX> ").strip()
                except EOFError:
                    line = "quit"
                except KeyboardInterrupt:
                    line = "quit"

                if line.lower() in {"q", "quit", "exit"}:
                    break

                if not line:
                    continue

                try:
                    payload = bytes.fromhex(line)
                except ValueError:
                    print("Invalid hex. Example: 01 02 aa 55")
                    continue

                try:
                    ser.write(payload)
                    ser.flush()
                except Exception as exc:
                    msg = f"[{stamp()}] ERROR TX: {exc}"
                    print(msg)
                    log_line(msg)
                    break

                msg = f"[{stamp()}] TX {len(payload)} bytes: {to_hex(payload)}"
                if not args.quiet_tx:
                    print(msg)
                log_line(msg)
                add_tx_stats(len(payload))
                emit_summary()

        finally:
            stop_event.set()
            try:
                thread.join(timeout=0.5)
            except Exception:
                pass
            try:
                emit_summary(force=True)
                ser.close()
            except Exception:
                pass
            log_line(f"[{stamp()}] CLOSE")
            print("Closed.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
