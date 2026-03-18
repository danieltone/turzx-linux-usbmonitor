#!/usr/bin/env python3
"""
CubeSat Telemetry Demo for Turing 3.5" Display
Displays mock real-time CubeSat mission data like mission control.
"""
import sys
import os
import time
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'turing-smart-screen-python'))

from PIL import Image, ImageDraw, ImageFont
from library.lcd.lcd_comm_rev_a import LcdCommRevA
from library.lcd.lcd_comm import Orientation

W, H = 480, 320
PORT = '/dev/ttyACM0'

# CubeSat mock data generator
class CubeSatData:
    def __init__(self):
        self.base_altitude = 550000  # LEO altitude in meters
        self.base_speed = 7400  # m/s orbital velocity
        self.base_temp = -60  # solar panel temp in C
        self.start_time = datetime.now()
        
    def get_data(self):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        # Simulate orbital variations
        alt_variation = random.randint(-30, 30) + int(20 * (elapsed % 600) / 600)
        speed_variation = random.randint(-5, 5)
        temp_variation = random.randint(-3, 3)
        signal = 92 + random.randint(-10, 10)
        power = 4.2 + random.uniform(-0.3, 0.3)
        
        return {
            'name': 'CUBESAT (FROGNET-23)',
            'altitude': self.base_altitude + alt_variation,
            'speed': self.base_speed + speed_variation,
            'temp': self.base_temp + temp_variation,
            'signal': min(100, max(0, signal)),
            'lat': 45.2156 + random.uniform(-1.0, 1.0),
            'lon': -15.3456 + random.uniform(-1.0, 1.0),
            'power': power,
            'uptime': int(elapsed),
        }

def get_font(size=20):
    try:
        return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', size)
    except:
        return ImageFont.load_default()

def format_number(n, decimals=0):
    if decimals == 0:
        return f"{int(n):,}"
    return f"{n:.{decimals}f}"

def make_telemetry_display(data):
    """Create a mission-control style telemetry display for CubeSat"""
    img = Image.new('RGB', (W, H), (15, 10, 25))  # Deep purple background
    draw = ImageDraw.Draw(img)
    
    # Header
    title_font = get_font(24)
    header_font = get_font(14)
    data_font = get_font(16)
    
    # Title
    title = "★ " + data['name'] + " ★"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    title_w = bbox[2] - bbox[0]
    draw.text(((W - title_w) // 2, 10), title, font=title_font, fill=(100, 200, 255))
    
    # Status line
    status_y = 50
    status = f"UPTIME: {data['uptime']:05d}s │ SIGNAL: {data['signal']:3.0f}% │ PWR: {data['power']:.1f}W"
    draw.text((10, status_y), status, font=header_font, fill=(0, 255, 150))
    
    # Primary data: Altitude, Speed
    item_y = 90
    item_h = 35
    
    # Left column: Altitude
    draw.text((15, item_y), "ALTITUDE", font=header_font, fill=(255, 150, 100))
    alt_str = f"{format_number(data['altitude'])} m"
    draw.text((15, item_y + 18), alt_str, font=data_font, fill=(100, 255, 150))
    
    # Right column: Speed
    draw.text((W - 200, item_y), "VELOCITY", font=header_font, fill=(255, 150, 100))
    speed_str = f"{format_number(data['speed'], 1)} m/s"
    draw.text((W - 200, item_y + 18), speed_str, font=data_font, fill=(100, 255, 150))
    
    # Secondary data: Temp, Position
    item_y = 160
    draw.text((15, item_y), "PANEL TEMP", font=header_font, fill=(255, 200, 100))
    temp_str = f"{data['temp']:.1f}°C"
    draw.text((15, item_y + 18), temp_str, font=data_font, fill=(255, 200, 100))
    
    # Position
    draw.text((W - 200, item_y), "COORDINATES", font=header_font, fill=(200, 150, 255))
    pos_str = f"{data['lat']:+.2f}°, {data['lon']:+.2f}°"
    draw.text((W - 200, item_y + 18), pos_str, font=data_font, fill=(200, 200, 255))
    
    # Status bar at bottom
    status_bar_y = H - 25
    draw.rectangle([(0, status_bar_y), (W, H)], fill=(20, 15, 40))
    
    status_text = "● MISSION ACTIVE ● PAYLOAD: ON DUTY ● LINK: EXCELLENT"
    bbox = draw.textbbox((0, 0), status_text, font=header_font)
    text_w = bbox[2] - bbox[0]
    draw.text(((W - text_w) // 2, status_bar_y + 2), status_text, font=header_font, fill=(100, 255, 200))
    
    return img

def main():
    print('Connecting to display...', flush=True)
    lcd = LcdCommRevA(com_port=PORT, display_width=320, display_height=480)
    lcd.InitializeComm()
    lcd.SetOrientation(Orientation.LANDSCAPE)
    
    print('Generating CubeSat telemetry display...', flush=True)
    cubesat_data = CubeSatData()
    
    print('Streaming live CubeSat telemetry (Ctrl+C to stop)...', flush=True)
    try:
        while True:
            data = cubesat_data.get_data()
            img = make_telemetry_display(data)
            lcd.DisplayPILImage(img)
            print(f"  {data['name']} | Alt: {format_number(data['altitude'])}m | Speed: {format_number(data['speed'], 1)}m/s | Temp: {data['temp']:.1f}°C | Pwr: {data['power']:.1f}W", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print('\nMission telemetry ended.', flush=True)
    finally:
        del lcd

if __name__ == '__main__':
    main()
