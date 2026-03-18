#!/usr/bin/env python3
import argparse
import pathlib
import subprocess
from typing import Iterable


def parse_meta(meta_path: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not meta_path.exists():
        return values
    for raw in meta_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def normalize_capdata(capdata: str) -> str:
    clean = capdata.strip().replace(":", " ").lower()
    chunks = [part for part in clean.split() if part]
    return " ".join(chunks)


def is_out_endpoint(endpoint_hex: str) -> bool:
    endpoint_hex = endpoint_hex.strip().lower()
    if endpoint_hex.startswith("0x"):
        endpoint_hex = endpoint_hex[2:]
    try:
        endpoint_val = int(endpoint_hex, 16)
    except ValueError:
        return False
    return (endpoint_val & 0x80) == 0


def tshark_lines(pcap: pathlib.Path, dev_addr: str | None) -> Iterable[str]:
    display_filter = "usb"
    if dev_addr is not None and str(dev_addr).strip() != "":
        display_filter += f" && usb.device_address == {dev_addr}"

    cmd = [
        "tshark",
        "-r",
        str(pcap),
        "-Y",
        display_filter,
        "-T",
        "fields",
        "-e",
        "frame.time_epoch",
        "-e",
        "usb.endpoint_address",
        "-e",
        "usb.urb_type",
        "-e",
        "usbcom.data.out_payload",
        "-e",
        "usbcom.data.in_payload",
        "-e",
        "usb.capdata",
        "-e",
        "usb.data_fragment",
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    for line in proc.stdout.splitlines():
        if line.strip():
            yield line


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract candidate host->device payload frames from USB capture into frames file"
    )
    parser.add_argument("--pcap", required=True, help="Path to .pcapng capture")
    parser.add_argument(
        "--meta",
        default=None,
        help="Optional metadata file from capture_usbmonitor.sh (default: <pcap>.meta)",
    )
    parser.add_argument(
        "--device-address",
        default=None,
        help="USB device address override (e.g., 6). If omitted, tries meta file.",
    )
    parser.add_argument(
        "--all-devices",
        action="store_true",
        help="Disable device-address filter and parse payloads from all USB device addresses",
    )
    parser.add_argument(
        "--out",
        default="frames_probe.txt",
        help="Output frame list file (default: frames_probe.txt)",
    )
    parser.add_argument(
        "--out-rx",
        default="frames_rx_observed.txt",
        help="Output observed RX payload file (default: frames_rx_observed.txt)",
    )
    parser.add_argument(
        "--min-bytes",
        type=int,
        default=1,
        help="Minimum payload length to include",
    )
    parser.add_argument(
        "--unique",
        action="store_true",
        help="Keep only first occurrence of each payload",
    )
    args = parser.parse_args()

    pcap = pathlib.Path(args.pcap)
    if not pcap.exists():
        print(f"ERROR: pcap not found: {pcap}")
        return 1

    meta_path = pathlib.Path(args.meta) if args.meta else pathlib.Path(str(pcap) + ".meta")
    meta = parse_meta(meta_path)

    if args.all_devices:
        dev_addr = None
    else:
        dev_addr = args.device_address or meta.get("device_address")

    tx_frames: list[str] = []
    rx_frames: list[str] = []
    seen_tx: set[str] = set()
    seen_rx: set[str] = set()

    for line in tshark_lines(pcap, dev_addr):
        fields = line.split("\t")
        if len(fields) < 7:
            continue
        _, endpoint, urb_type, out_payload, in_payload, capdata, data_fragment = (
            fields[0],
            fields[1],
            fields[2],
            fields[3],
            fields[4],
            fields[5],
            fields[6],
        )

        candidate_payload = ""
        if out_payload.strip():
            candidate_payload = out_payload
        elif in_payload.strip():
            candidate_payload = in_payload
        elif capdata.strip():
            candidate_payload = capdata
        elif data_fragment.strip():
            candidate_payload = data_fragment

        payload = normalize_capdata(candidate_payload)
        if not payload:
            continue

        payload_len = len(payload.split())
        if payload_len < args.min_bytes:
            continue

        is_submit = urb_type.strip().strip("'") == "S"
        is_complete = urb_type.strip().strip("'") == "C"

        if is_out_endpoint(endpoint) and is_submit:
            if args.unique and payload in seen_tx:
                continue
            tx_frames.append(payload)
            seen_tx.add(payload)
        elif (not is_out_endpoint(endpoint)) and is_complete:
            if args.unique and payload in seen_rx:
                continue
            rx_frames.append(payload)
            seen_rx.add(payload)

    out_path = pathlib.Path(args.out)
    out_rx_path = pathlib.Path(args.out_rx)

    header = [
        "# Auto-generated from USB capture",
        f"# pcap={pcap}",
        f"# meta={meta_path if meta_path.exists() else 'n/a'}",
        f"# device_address={dev_addr if dev_addr is not None else 'all'}",
        f"# tx_frames={len(tx_frames)}",
        "",
    ]
    out_path.write_text("\n".join(header + tx_frames) + "\n", encoding="utf-8")

    header_rx = [
        "# Observed device->host payloads",
        f"# rx_frames={len(rx_frames)}",
        "",
    ]
    out_rx_path.write_text("\n".join(header_rx + rx_frames) + "\n", encoding="utf-8")

    print(f"Wrote TX probe frames: {out_path} ({len(tx_frames)} frames)")
    print(f"Wrote RX observed frames: {out_rx_path} ({len(rx_frames)} frames)")
    if len(tx_frames) == 0:
        print("No TX frames extracted. Try removing --device-address filter or recapturing.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
