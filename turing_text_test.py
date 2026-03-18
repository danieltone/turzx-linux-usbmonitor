#!/usr/bin/env python3
"""
Display text on the Turing UsbMonitor 3.5" (rev A, 1a86:5722).
Usage: python3 turing_text_test.py "Hello World"
"""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'turing-smart-screen-python'))

from PIL import Image, ImageDraw, ImageFont
from library.lcd.lcd_comm_rev_a import LcdCommRevA
from library.lcd.lcd_comm import Orientation

W, H = 480, 320
PORT = '/dev/ttyACM0'


def make_text_image(lines, bg=(0, 0, 0), fg=(255, 255, 255), font_size=40):
    img = Image.new('RGB', (W, H), bg)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', font_size)
    except Exception:
        font = ImageFont.load_default()

    total_h = len(lines) * (font_size + 10)
    y = (H - total_h) // 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (W - text_w) // 2
        draw.text((x, y), line, font=font, fill=fg)
        y += font_size + 10
    return img


def main():
    messages = sys.argv[1:] if len(sys.argv) > 1 else ['TEST 1', 'TEST 2', 'TEST 3']

    print(f'Connecting to {PORT}...', flush=True)
    lcd = LcdCommRevA(com_port=PORT, display_width=320, display_height=480)
    lcd.InitializeComm()
    lcd.SetOrientation(Orientation.LANDSCAPE)

    for i, msg in enumerate(messages):
        print(f'Displaying: {msg}', flush=True)
        colors = [
            ((0, 0, 128), (255, 255, 0)),   # blue bg, yellow text
            ((0, 100, 0), (255, 255, 255)),  # green bg, white text
            ((128, 0, 0), (255, 255, 255)),  # red bg, white text
        ]
        bg, fg = colors[i % len(colors)]
        img = make_text_image([msg], bg=bg, fg=fg, font_size=60)
        lcd.DisplayPILImage(img)
        print(f'  shown - holding 3s', flush=True)
        time.sleep(3)

    # Final: show all messages together
    print('Displaying all messages together...', flush=True)
    img = make_text_image(messages, bg=(20, 20, 20), fg=(0, 255, 200), font_size=40)
    lcd.DisplayPILImage(img)
    print('Done.', flush=True)
    del lcd


if __name__ == '__main__':
    main()
