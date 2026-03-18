#!/usr/bin/env python3
import argparse
import datetime as dt
import os
import time

import serial
from serial import SerialTimeoutException
from PIL import Image, ImageDraw, ImageFont


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def encode_window_command(cmd: int, x1: int, y1: int, x2: int, y2: int, payload: bytes | None = None) -> bytes:
    if payload is None:
        packet = bytearray(6)
    else:
        packet = bytearray(payload)
        if len(packet) < 6:
            packet.extend(b"\x00" * (6 - len(packet)))

    packet[0] = (x1 >> 2) & 0xFF
    packet[1] = ((x1 & 0x03) << 6) | ((y1 >> 4) & 0x3F)
    packet[2] = ((y1 & 0x0F) << 4) | ((x2 >> 6) & 0x0F)
    packet[3] = ((x2 & 0x3F) << 2) | ((y2 >> 8) & 0x03)
    packet[4] = y2 & 0xFF
    packet[5] = cmd & 0xFF
    return bytes(packet)


def rgb888_to_rgb565_be_bytes(image: Image.Image, swap_rb: bool = False, swap_bytes: bool = False) -> bytes:
    rgb = image.convert("RGB")
    raw = bytearray()
    for red, green, blue in rgb.getdata():
        if swap_rb:
            red, blue = blue, red
        value = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
        high = (value >> 8) & 0xFF
        low = value & 0xFF
        if swap_bytes:
            raw.append(low)
            raw.append(high)
        else:
            raw.append(high)
            raw.append(low)
    return bytes(raw)


def apply_transform(image: Image.Image, rotate: int, flip_x: bool, flip_y: bool) -> Image.Image:
    out = image
    rotate_map = {
        0: None,
        90: Image.Transpose.ROTATE_90,
        180: Image.Transpose.ROTATE_180,
        270: Image.Transpose.ROTATE_270,
    }
    op = rotate_map.get(rotate)
    if op is not None:
        out = out.transpose(op)
    if flip_x:
        out = out.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flip_y:
        out = out.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return out


def make_color_bars(width: int, height: int) -> Image.Image:
    image = Image.new("RGB", (width, height), color=(0, 0, 0))
    draw = ImageDraw.Draw(image)
    colors = [
        (255, 255, 255),
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (0, 255, 255),
        (255, 0, 255),
        (0, 0, 0),
    ]
    bar_w = max(1, width // len(colors))
    for i, color in enumerate(colors):
        x1 = i * bar_w
        x2 = width - 1 if i == len(colors) - 1 else ((i + 1) * bar_w - 1)
        draw.rectangle((x1, 0, x2, height - 1), fill=color)
    return image


def make_text_frame(width: int, height: int, text: str, bg=(0, 0, 0), fg=(255, 255, 255)) -> Image.Image:
    image = Image.new("RGB", (width, height), color=bg)
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=max(24, min(width, height) // 6))
    except Exception:
        font = ImageFont.load_default()

    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    text_width = right - left
    text_height = bottom - top

    x = (width - text_width) // 2
    y = (height - text_height) // 2

    draw.text((x, y), text, font=font, fill=fg)
    return image


def send_full_frame(ser: serial.Serial, pixel_data: bytes, width: int, height: int, mode: str) -> None:
    x1, y1, x2, y2 = 0, 0, width - 1, height - 1

    if mode == "cmd194":
        packet = encode_window_command(194, x1, y1, x2, y2, payload=pixel_data)
        ser.write(packet)
        ser.flush()
        return

    if mode == "cmd198":
        command = encode_window_command(198, x1, y1, x2, y2)
        ser.write(command)
        ser.write(pixel_data)
        ser.flush()
        return

    command = encode_window_command(197, x1, y1, x2, y2)
    ser.write(command)
    ser.write(pixel_data)
    ser.flush()


def write_all_chunks(ser: serial.Serial, data: bytes, chunk_size: int) -> None:
    if chunk_size <= 0:
        ser.write(data)
        return
    offset = 0
    total = len(data)
    while offset < total:
        end = min(offset + chunk_size, total)
        chunk = data[offset:end]
        written = ser.write(chunk)
        if written is None:
            written = 0
        if written <= 0:
            raise SerialTimeoutException("serial write returned 0 bytes")
        offset += written


def send_full_frame_chunked(ser: serial.Serial, pixel_data: bytes, width: int, height: int, mode: str, chunk_size: int) -> None:
    x1, y1, x2, y2 = 0, 0, width - 1, height - 1

    if mode == "cmd194":
        packet = encode_window_command(194, x1, y1, x2, y2, payload=pixel_data)
        write_all_chunks(ser, packet, chunk_size)
        ser.flush()
        return

    if mode == "cmd198":
        command = encode_window_command(198, x1, y1, x2, y2)
        write_all_chunks(ser, command, chunk_size)
        write_all_chunks(ser, pixel_data, chunk_size)
        ser.flush()
        return

    command = encode_window_command(197, x1, y1, x2, y2)
    write_all_chunks(ser, command, chunk_size)
    write_all_chunks(ser, pixel_data, chunk_size)
    ser.flush()


def main() -> int:
    parser = argparse.ArgumentParser(description="Direct text-to-screen test for Turing USB monitor")
    parser.add_argument("--port", default="/dev/ttyACM0", help="USB CDC port path")
    parser.add_argument("--baud", type=int, default=115200, help="Baud (API-required; CDC often ignores)")
    parser.add_argument("--width", type=int, default=480, help="Screen width in pixels")
    parser.add_argument("--height", type=int, default=320, help="Screen height in pixels")
    parser.add_argument("--mode", choices=["cmd197", "cmd198", "cmd194"], default="cmd197", help="Transfer mode")
    parser.add_argument("--pattern", choices=["text", "bars"], default="text", help="Frame pattern type")
    parser.add_argument("--chunk-size", type=int, default=1024, help="Serial write chunk size in bytes")
    parser.add_argument("--write-timeout", type=float, default=2.0, help="Serial write timeout seconds")
    parser.add_argument("--rotate", type=int, choices=[0, 90, 180, 270], default=0, help="Rotate frame before send")
    parser.add_argument("--flip-x", action="store_true", help="Flip frame horizontally before send")
    parser.add_argument("--flip-y", action="store_true", help="Flip frame vertically before send")
    parser.add_argument("--swap-rb", action="store_true", help="Swap red/blue channels before RGB565 conversion")
    parser.add_argument("--swap-bytes", action="store_true", help="Swap high/low bytes of each RGB565 pixel")
    parser.add_argument("--bg", default="000000", help="Background hex color, e.g. 000000")
    parser.add_argument("--fg", default="ffffff", help="Foreground hex color, e.g. ffffff")
    parser.add_argument("--hold", type=float, default=1.0, help="Seconds between frames")
    parser.add_argument("texts", nargs="*", default=["TEST1", "TEST2", "TEST3"], help="Texts to display in order")
    args = parser.parse_args()

    def parse_hex_color(value: str) -> tuple[int, int, int]:
        value = value.strip().lstrip("#")
        if len(value) != 6:
            raise ValueError(f"Invalid color: {value}")
        return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)

    bg = parse_hex_color(args.bg)
    fg = parse_hex_color(args.fg)

    os.makedirs("logs", exist_ok=True)
    log_path = os.path.join("logs", dt.datetime.now().strftime("display_text_%Y%m%d_%H%M%S.log"))

    with open(log_path, "a", encoding="utf-8") as log:
        def log_line(message: str) -> None:
            line = f"[{now_stamp()}] {message}"
            print(line)
            log.write(line + "\n")
            log.flush()

        try:
            ser = serial.Serial(args.port, args.baud, timeout=0.1, write_timeout=max(0.1, args.write_timeout))
        except Exception as exc:
            log_line(f"ERROR open {args.port}: {exc}")
            return 1

        try:
            log_line(
                "OPEN "
                f"port={args.port} baud={args.baud} mode={args.mode} size={args.width}x{args.height} "
                f"pattern={args.pattern} rotate={args.rotate} flip_x={args.flip_x} flip_y={args.flip_y} "
                f"swap_rb={args.swap_rb} swap_bytes={args.swap_bytes}"
            )
            for text in args.texts:
                if args.pattern == "bars":
                    frame = make_color_bars(args.width, args.height)
                else:
                    frame = make_text_frame(args.width, args.height, text, bg=bg, fg=fg)
                frame = apply_transform(frame, args.rotate, args.flip_x, args.flip_y)
                frame_path = os.path.join("logs", f"frame_{text}_{int(time.time())}.png")
                frame.save(frame_path)
                pixel_data = rgb888_to_rgb565_be_bytes(frame, swap_rb=args.swap_rb, swap_bytes=args.swap_bytes)
                log_line(f"TX_START text='{text}' bytes={len(pixel_data)}")
                send_full_frame_chunked(ser, pixel_data, frame.width, frame.height, args.mode, args.chunk_size)
                log_line(f"SENT text='{text}' bytes={len(pixel_data)} png={frame_path}")
                time.sleep(max(0.0, args.hold))
        except SerialTimeoutException as exc:
            log_line(f"ERROR serial timeout: {exc}")
            return 2
        except Exception as exc:
            log_line(f"ERROR send: {exc}")
            return 3
        finally:
            try:
                ser.close()
            except Exception:
                pass
            log_line("CLOSE")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
