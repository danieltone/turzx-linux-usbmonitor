#!/usr/bin/env python3
"""
Minimal color test using turing-smart-screen-python library (rev A / UsbMonitor).
Device: 1a86:5722 /dev/ttyACM0  -- SubRevision USBMONITOR_3_5
"""
import sys
import time
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'turing-smart-screen-python'))

from PIL import Image
from library.lcd.lcd_comm_rev_a import LcdCommRevA
from library.lcd.lcd_comm import Orientation

COLORS = [
    ('red',   (255, 0, 0)),
    ('green', (0, 255, 0)),
    ('blue',  (0, 0, 255)),
    ('white', (255, 255, 255)),
    ('black', (0, 0, 0)),
]

def solid_image(w, h, rgb):
    return Image.new('RGB', (w, h), rgb)

def main():
    port = '/dev/ttyACM0'
    print(f'Connecting to {port} (rev A / UsbMonitor)...', flush=True)
    lcd = LcdCommRevA(com_port=port, display_width=320, display_height=480)

    print('Running InitializeComm...', flush=True)
    lcd.InitializeComm()

    print('Setting orientation to landscape...', flush=True)
    lcd.SetOrientation(Orientation.LANDSCAPE)

    w, h = lcd.get_width(), lcd.get_height()
    print(f'Display size reported: {w}x{h}', flush=True)

    for name, rgb in COLORS:
        print(f'Displaying {name} {rgb}...', flush=True)
        img = solid_image(w, h, rgb)
        lcd.DisplayPILImage(img)
        print(f'{name} sent - holding 3s', flush=True)
        time.sleep(3)

    print('All done.', flush=True)
    del lcd

if __name__ == '__main__':
    main()
