#!/usr/bin/env bash
set -euo pipefail

VIDPID="1a86:5722"
OUTFILE=""
DURATION="0"

usage() {
  cat <<'EOF'
Usage: capture_usbmonitor.sh [--vidpid 1a86:5722] [--outfile path.pcapng] [--duration seconds]

Captures USB monitor traffic from usbmon on the bus where the target device is attached.
Usually run with sudo.

Examples:
  sudo ./capture_usbmonitor.sh
  sudo ./capture_usbmonitor.sh --duration 30
  sudo ./capture_usbmonitor.sh --outfile ./logs/usbcap_test.pcapng
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vidpid)
      VIDPID="$2"
      shift 2
      ;;
    --outfile)
      OUTFILE="$2"
      shift 2
      ;;
    --duration)
      DURATION="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 2
      ;;
  esac
done

if ! command -v lsusb >/dev/null 2>&1; then
  echo "ERROR: lsusb not found"
  exit 1
fi
if ! command -v tshark >/dev/null 2>&1; then
  echo "ERROR: tshark not found"
  exit 1
fi

LSUSB_LINE="$(lsusb -d "$VIDPID" | head -n 1 || true)"
if [[ -z "$LSUSB_LINE" ]]; then
  echo "ERROR: device $VIDPID not found via lsusb"
  exit 1
fi

BUS_STR="$(awk '{print $2}' <<<"$LSUSB_LINE")"
DEV_STR="$(awk '{print $4}' <<<"$LSUSB_LINE" | tr -d ':')"
BUS_NUM="$((10#$BUS_STR))"
DEV_NUM="$((10#$DEV_STR))"

mkdir -p ./logs
if [[ -z "$OUTFILE" ]]; then
  TS="$(date +%Y%m%d_%H%M%S)"
  OUTFILE="./logs/usbcap_${VIDPID/:/_}_${TS}.pcapng"
fi
META_FILE="${OUTFILE}.meta"

cat > "$META_FILE" <<EOF
vidpid=$VIDPID
bus=$BUS_NUM
device_address=$DEV_NUM
captured_at=$(date --iso-8601=seconds)
EOF

INTERFACE="usbmon${BUS_NUM}"

if ! tshark -D | grep -q "${INTERFACE}"; then
  echo "Interface ${INTERFACE} not present. Trying to load usbmon module..."
  if sudo -n modprobe usbmon >/dev/null 2>&1; then
    echo "usbmon module loaded."
  else
    echo "Could not auto-load usbmon via sudo -n."
  fi
fi

if ! tshark -D | grep -q "${INTERFACE}"; then
  echo "ERROR: ${INTERFACE} still unavailable."
  echo "Try: sudo modprobe usbmon"
  exit 1
fi

echo "Found device: $LSUSB_LINE"
echo "Capturing on interface: $INTERFACE"
echo "Output: $OUTFILE"
echo "Metadata: $META_FILE"

if [[ "$DURATION" == "0" ]]; then
  echo "Capture running until Ctrl+C..."
  tshark -i "$INTERFACE" -w "$OUTFILE"
else
  echo "Capture running for $DURATION seconds..."
  timeout "$DURATION" tshark -i "$INTERFACE" -w "$OUTFILE" || true
  echo "Capture complete."
fi
