#!/usr/bin/env python3
# Protocol: XuanFang / Turing rev B - 10-byte framed packets [cmd, 8-byte payload, cmd]
# Identified by VID:PID 1a86:5722
# Reference: turing-smart-screen-python lcd_comm_rev_b.py
import os
import time
import termios
import select

CMD_HELLO          = 0xCA
CMD_SET_ORIENT     = 0xCB
CMD_DISPLAY_BITMAP = 0xCC
CMD_SET_BRIGHTNESS = 0xCE

# RGB565 big-endian colors
COLORS = {
    'white': b'\xff\xff',
    'red':   b'\xf8\x00',
    'green': b'\x07\xe0',
    'blue':  b'\x00\x1f',
    'black': b'\x00\x00',
}


def make_packet(cmd, payload=()):
    """Build a 10-byte framed command packet."""
    buf = bytearray(10)
    buf[0] = cmd
    for i, b in enumerate(payload[:8]):
        buf[1 + i] = b
    buf[9] = cmd
    return bytes(buf)


def setup_serial(fd, speed=termios.B115200):
    attrs = termios.tcgetattr(fd)
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attrs[3] = 0
    attrs[4] = speed
    attrs[5] = speed
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    termios.tcflush(fd, termios.TCIOFLUSH)


def write_all(fd, data, chunk=2560):
    total = len(data)
    sent = 0
    while sent < total:
        end = min(sent + chunk, total)
        n = os.write(fd, data[sent:end])
        if n <= 0:
            raise RuntimeError('write returned 0')
        sent += n
        if sent % 65536 == 0:
            print(f'  pixels sent {sent}/{total}', flush=True)
        time.sleep(0.001)


def main():
    print('open /dev/ttyACM0', flush=True)
    fd = os.open('/dev/ttyACM0', os.O_RDWR | os.O_NOCTTY)
    try:
        setup_serial(fd)

        # HELLO handshake - required before display accepts frames
        hello_payload = [ord('H'), ord('E'), ord('L'), ord('L'), ord('O')]
        print('sending HELLO (0xCA)...', flush=True)
        os.write(fd, make_packet(CMD_HELLO, hello_payload))
        # Read response with timeout (device may not reply if already in a state)
        rlist, _, _ = select.select([fd], [], [], 2.0)
        if rlist:
            response = os.read(fd, 10)
            print(f'HELLO response ({len(response)} bytes): {response.hex()}', flush=True)
        else:
            print('no HELLO response within 2s - continuing anyway', flush=True)

        # Landscape orientation
        os.write(fd, make_packet(CMD_SET_ORIENT, [0x01]))
        time.sleep(0.05)

        w, h = 480, 320
        for name, pixel in COLORS.items():
            print(f'display {name}...', flush=True)
            # DISPLAY_BITMAP payload: x0_hi, x0_lo, y0_hi, y0_lo, x1_hi, x1_lo, y1_hi, y1_lo
            coord_payload = [0, 0, 0, 0, (w-1) >> 8, (w-1) & 0xFF, (h-1) >> 8, (h-1) & 0xFF]
            os.write(fd, make_packet(CMD_DISPLAY_BITMAP, coord_payload))
            write_all(fd, pixel * (w * h))
            time.sleep(0.05)
            print(f'{name} done - holding 2s', flush=True)
            time.sleep(2.0)
    finally:
        os.close(fd)
    print('all done', flush=True)


if __name__ == '__main__':
    main()
