#!/usr/bin/env python3
import argparse
import csv
import glob
import os
import time
from typing import Optional


RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"


def split_base_ext(path: str) -> tuple[str, str]:
    stem, ext = os.path.splitext(path)
    if not ext:
        ext = ".csv"
    return stem, ext


def find_latest_csv(base_path: str, daily: bool) -> Optional[str]:
    stem, ext = split_base_ext(base_path)
    candidates = []

    if os.path.exists(base_path):
        candidates.append(base_path)

    if daily:
        pattern = f"{stem}_*{ext}"
        candidates.extend(glob.glob(pattern))

    candidates = [path for path in candidates if os.path.isfile(path)]
    if not candidates:
        return None

    return max(candidates, key=lambda path: os.path.getmtime(path))


def to_float(value: str) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def to_int(value: str) -> int:
    try:
        return int(float(value))
    except Exception:
        return 0


def use_color(mode: str) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    return os.isatty(1)


def colorize(text: str, color: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{color}{text}{RESET}"


def read_new_rows(path: str, state: dict) -> list[dict]:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        all_rows = list(csv.DictReader(handle))

    processed = state.get("rows_processed", 0)
    if processed < 0:
        processed = 0

    if len(all_rows) < processed:
        processed = 0

    new_rows = all_rows[processed:]
    state["rows_processed"] = len(all_rows)
    return new_rows


def count_rows(path: str) -> int:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def compute_rates(prev: Optional[dict], curr: dict) -> Optional[dict]:
    if prev is None:
        return None

    curr_epoch = to_float(curr.get("epoch", "0"))
    prev_epoch = to_float(prev.get("epoch", "0"))
    dt = curr_epoch - prev_epoch
    if dt <= 0:
        return None

    tx_frames = to_int(curr.get("tx_frames", "0")) - to_int(prev.get("tx_frames", "0"))
    tx_bytes = to_int(curr.get("tx_bytes", "0")) - to_int(prev.get("tx_bytes", "0"))
    rx_packets = to_int(curr.get("rx_packets", "0")) - to_int(prev.get("rx_packets", "0"))
    rx_bytes = to_int(curr.get("rx_bytes", "0")) - to_int(prev.get("rx_bytes", "0"))

    if tx_frames < 0 or tx_bytes < 0 or rx_packets < 0 or rx_bytes < 0:
        return None

    return {
        "tx_frames_s": tx_frames / dt,
        "tx_bytes_s": tx_bytes / dt,
        "rx_packets_s": rx_packets / dt,
        "rx_bytes_s": rx_bytes / dt,
    }


def format_rate_text(rates: Optional[dict]) -> str:
    if rates is None:
        return "rates: n/a"
    return (
        f"rates: tx_frames/s={rates['tx_frames_s']:.2f} tx_B/s={rates['tx_bytes_s']:.2f} "
        f"rx_pkts/s={rates['rx_packets_s']:.2f} rx_B/s={rates['rx_bytes_s']:.2f}"
    )


def rate_state(value: float, low: float, high: float) -> str:
    if value < low:
        return "low"
    if value > high:
        return "high"
    return "ok"


def print_row(path: str, prev: Optional[dict], row: dict, args: argparse.Namespace) -> None:
    stamp = row.get("timestamp", "")
    kind = row.get("kind", "")
    tx_frames = to_int(row.get("tx_frames", "0"))
    tx_bytes = to_int(row.get("tx_bytes", "0"))
    rx_packets = to_int(row.get("rx_packets", "0"))
    rx_bytes = to_int(row.get("rx_bytes", "0"))
    rates = compute_rates(prev, row)
    rates_text = format_rate_text(rates)

    color_on = use_color(args.color)
    alert_text = ""
    if rates is not None:
        rx_state = rate_state(rates["rx_bytes_s"], args.rx_low, args.rx_high)
        tx_state = rate_state(rates["tx_bytes_s"], args.tx_low, args.tx_high)

        tags = []
        if rx_state != "ok":
            tags.append(f"RX_{rx_state.upper()}")
        if tx_state != "ok":
            tags.append(f"TX_{tx_state.upper()}")

        if tags:
            alert_text = " alerts=" + ",".join(tags)
            if rx_state == "low" or tx_state == "low":
                alert_text = colorize(alert_text, YELLOW, color_on)
            if rx_state == "high" or tx_state == "high":
                alert_text = colorize(alert_text, RED, color_on)
        else:
            alert_text = colorize(" alerts=OK", GREEN, color_on)

    print(
        f"[{stamp}] file={os.path.basename(path)} kind={kind} "
        f"totals: tx_frames={tx_frames} tx_bytes={tx_bytes} "
        f"rx_packets={rx_packets} rx_bytes={rx_bytes} | {rates_text}{alert_text}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Watch summary CSV output and print live TX/RX rates"
    )
    parser.add_argument(
        "--csv-base",
        default="./logs/summary.csv",
        help="Base CSV path used by --summary-csv in the main tester",
    )
    parser.add_argument(
        "--daily",
        action="store_true",
        help="Watch date-suffixed files too (for --summary-csv-daily)",
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=1.0,
        help="Polling interval in seconds",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Print currently available new rows once and exit",
    )
    parser.add_argument(
        "--replay-history",
        action="store_true",
        help="On startup/file switch, replay existing rows instead of only new appended rows",
    )
    parser.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="Color mode for alerts: auto (default), always, never",
    )
    parser.add_argument(
        "--rx-low",
        type=float,
        default=1.0,
        help="RX bytes/sec lower threshold for LOW alert",
    )
    parser.add_argument(
        "--rx-high",
        type=float,
        default=1000000.0,
        help="RX bytes/sec upper threshold for HIGH alert",
    )
    parser.add_argument(
        "--tx-low",
        type=float,
        default=1.0,
        help="TX bytes/sec lower threshold for LOW alert",
    )
    parser.add_argument(
        "--tx-high",
        type=float,
        default=1000000.0,
        help="TX bytes/sec upper threshold for HIGH alert",
    )
    args = parser.parse_args()

    if args.poll <= 0:
        print("ERROR: --poll must be > 0")
        return 2
    if args.rx_low > args.rx_high:
        print("ERROR: --rx-low must be <= --rx-high")
        return 2
    if args.tx_low > args.tx_high:
        print("ERROR: --tx-low must be <= --tx-high")
        return 2

    print("Watching summary CSV for updates...")
    print(f"base={args.csv_base} daily={args.daily} poll={args.poll}s")

    state = {"path": None, "rows_processed": 0}
    prev_row: Optional[dict] = None

    while True:
        path = find_latest_csv(args.csv_base, args.daily)
        if path is None:
            if args.once:
                print("No CSV file found yet.")
                return 0
            time.sleep(args.poll)
            continue

        if state["path"] != path:
            state["path"] = path
            if args.replay_history:
                state["rows_processed"] = 0
            else:
                try:
                    state["rows_processed"] = count_rows(path)
                except Exception:
                    state["rows_processed"] = 0
            print(f"Switched to: {path}")

        try:
            rows = read_new_rows(path, state)
        except Exception as exc:
            print(f"ERROR reading {path}: {exc}")
            time.sleep(args.poll)
            continue

        for row in rows:
            print_row(path, prev_row, row, args)
            prev_row = row

        if args.once:
            return 0

        time.sleep(args.poll)


if __name__ == "__main__":
    raise SystemExit(main())
