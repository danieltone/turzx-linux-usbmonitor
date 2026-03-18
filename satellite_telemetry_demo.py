#!/usr/bin/env python3
"""
Satellite Telemetry Demo for Turing 3.5" Display
Displays mock real-time satellite data like mission control.
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

# Satellite mock data generator
class SatelliteData:
    def __init__(self):
        self.base_altitude = 408000  # ISS altitude in meters
        self.base_speed = 7660  # m/s orbital velocity
        self.base_temp = -75  # external temp in C
        self.start_time = datetime.now()
        
    def get_data(self):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        # Simulate orbital variations
        alt_variation = random.randint(-50, 50) + int(30 * (elapsed % 600) / 600)
        speed_variation = random.randint(-10, 10)
        temp_variation = random.randint(-5, 5)
        signal = 85 + random.randint(-8, 8)
        
        return {
            'name': 'ISS (ZARYA)',
            'altitude': self.base_altitude + alt_variation,
            'speed': self.base_speed + speed_variation,
            'temp': self.base_temp + temp_variation,
            'signal': min(100, max(0, signal)),
            'lat': 51.6416 + random.uniform(-0.5, 0.5),
            'lon': -0.0890 + random.uniform(-0.5, 0.5),
            'batt': 98 + random.randint(-2, 2),
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
    """Create a mission-control style telemetry display"""
    img = Image.new('RGB', (W, H), (10, 10, 30))  # Deep blue background
    draw = ImageDraw.Draw(img)
    
    # Header
    title_font = get_font(24)
    header_font = get_font(14)
    data_font = get_font(16)
    
    # Title
    title = "◆ " + data['name'] + " ◆"
    bbox = draw.textbbox((0, 0), title, font=title_font)
    title_w = bbox[2] - bbox[0]
    draw.text(((W - title_w) // 2, 10), title, font=title_font, fill=(0, 255, 200))
    
    # Status line
    status_y = 50
    status = f"UPTIME: {data['uptime']:05d}s │ SIGNAL: {data['signal']:3.0f}% │ BATT: {data['batt']:.0f}%"
    draw.text((10, status_y), status, font=header_font, fill=(100, 200, 100))
    
    # Primary data: Altitude, Speed
    item_y = 90
    item_h = 35
    
    # Left column: Altitude
    draw.text((15, item_y), "ALTITUDE", font=header_font, fill=(255, 100, 100))
    alt_str = f"{format_number(data['altitude'])} m"
    draw.text((15, item_y + 18), alt_str, font=data_font, fill=(100, 255, 100))
    
    # Right column: Speed
    draw.text((W - 200, item_y), "VELOCITY", font=header_font, fill=(255, 100, 100))
    speed_str = f"{format_number(data['speed'], 1)} m/s"
    draw.text((W - 200, item_y + 18), speed_str, font=data_font, fill=(100, 255, 100))
    
    # Secondary data: Temp, Position
    item_y = 160
    draw.text((15, item_y), "EXTERNAL TEMP", font=header_font, fill=(255, 150, 100))
    temp_str = f"{data['temp']:.1f}°C"
    draw.text((15, item_y + 18), temp_str, font=data_font, fill=(255, 200, 100))
    
    # Position
    draw.text((W - 200, item_y), "POSITION", font=header_font, fill=(255, 150, 100))
    pos_str = f"{data['lat']:+.2f}°, {data['lon']:+.2f}°"
    draw.text((W - 200, item_y + 18), pos_str, font=data_font, fill=(200, 150, 255))
    
    # Status bar at bottom
    status_bar_y = H - 25
    draw.rectangle([(0, status_bar_y), (W, H)], fill=(20, 20, 50))
    
    status_text = "● ACQUISITION ACTIVE ● DATA STREAM: NOMINAL ● COMM: STABLE"
    bbox = draw.textbbox((0, 0), status_text, font=header_font)
    text_w = bbox[2] - bbox[0]
    draw.text(((W - text_w) // 2, status_bar_y + 2), status_text, font=header_font, fill=(0, 255, 100))
    
    return img

def main():
    print('Connecting to display...', flush=True)
    lcd = LcdCommRevA(com_port=PORT, display_width=320, display_height=480)
    lcd.InitializeComm()
    lcd.SetOrientation(Orientation.LANDSCAPE)
    
    print('Generating telemetry display...', flush=True)
    sat_data = SatelliteData()
    
    print('Streaming live telemetry (Ctrl+C to stop)...', flush=True)
    try:
        while True:
            data = sat_data.get_data()
            img = make_telemetry_display(data)
            lcd.DisplayPILImage(img)
            print(f"  {data['name']} | Alt: {format_number(data['altitude'])}m | Speed: {format_number(data['speed'], 1)}m/s | Temp: {data['temp']:.1f}°C", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print('\nShutdown.', flush=True)
    finally:
        del lcd

if __name__ == '__main__':
    main()
