import network
import time
import gc9a01
from machine import Pin, SPI
import vga1_16x32 as font

# Import config
try:
    from config import *
    print("Config loaded")
except Exception as e:
    print(f"Config error: {e}")

# Color helper
def color565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

# Colors
BLACK = color565(0, 0, 0)
WHITE = color565(255, 255, 255)
GREEN = color565(0, 255, 0)
YELLOW = color565(255, 255, 0)
RED = color565(255, 0, 0)
BLUE = color565(100, 150, 255)
GRAY = color565(128, 128, 128)

tft = None

# Initialize display
def init_display():
    global tft
    print("Initializing display...")
    Pin(DISPLAY_BL, Pin.OUT).value(1)
    
    spi = SPI(DISPLAY_SPI_ID, baudrate=20_000_000, 
              sck=Pin(DISPLAY_SCK), mosi=Pin(DISPLAY_MOSI))
    
    tft = gc9a01.GC9A01(
        spi, DISPLAY_WIDTH, DISPLAY_HEIGHT,
        reset=Pin(DISPLAY_RST, Pin.OUT),
        dc=Pin(DISPLAY_DC, Pin.OUT),
        cs=Pin(DISPLAY_CS, Pin.OUT),
        rotation=0
    )
    tft.init()
    tft.fill(BLACK)
    print("Display OK")

# Connect to WiFi
def connect_wifi():
    print(f"Connecting to: {WIFI_SSID}")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if wlan.isconnected():
        print(f"Already connected: {wlan.ifconfig()[0]}")
        return True
    
    tft.fill(BLACK)
    tft.text(font, "WiFi...", 60, 100, BLUE)
    
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    
    timeout = 15
    while not wlan.isconnected() and timeout > 0:
        print(f"Waiting... {timeout}")
        time.sleep(1)
        timeout -= 1
    
    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print(f'WiFi Connected: {ip}')
        tft.fill(BLACK)
        tft.text(font, "Connected", 40, 100, GREEN)
        time.sleep(1)
        return True
    else:
        print('WiFi FAILED')
        tft.fill(BLACK)
        tft.text(font, "WiFi Fail", 40, 100, RED)
        return False

# Get current price from Tibber
def get_tibber_price():
    print("Fetching Tibber price...")
    query = """
    {
      viewer {
        homes {
          currentSubscription {
            priceInfo {
              current {
                total
                startsAt
              }
            }
          }
        }
      }
    }
    """
    
    headers = {
        'Authorization': f'Bearer {TIBBER_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    try:
        import urequests
        response = urequests.post(
            TIBBER_API_URL,
            headers=headers,
            json={'query': query}
        )
        
        data = response.json()
        response.close()
        
        price = data['data']['viewer']['homes'][0]['currentSubscription']['priceInfo']['current']['total']
        print(f"Price: {price} SEK/kWh")
        return price
        
    except Exception as e:
        print(f"Tibber API error: {e}")
        return None

# Draw price on display
def draw_price(price_sek):
    tft.fill(BLACK)
    
    if price_sek is None:
        tft.text(font, "API Error", 40, 100, RED)
        return
    
    price_ore = int(price_sek * 100)  # Convert to öre
    
    # Color based on price
    if price_ore < 50:
        price_color = GREEN
    elif price_ore < 100:
        price_color = YELLOW
    else:
        price_color = RED
    
    # Header
    tft.fill_rect(0, 0, DISPLAY_WIDTH, 40, BLUE)
    tft.text(font, "ELPRIS", 70, 8, WHITE)
    
    # Large price number
    price_text = str(price_ore)
    # Center the text
    text_x = (DISPLAY_WIDTH - len(price_text) * 16) // 2
    tft.text(font, price_text, text_x, 80, price_color)
    
    # Unit label
    tft.text(font, "ore/kWh", 50, 120, WHITE)
    
    # Draw a horizontal bar showing relative price
    bar_width = 180
    bar_x = (DISPLAY_WIDTH - bar_width) // 2
    bar_y = 170
    
    # Background
    tft.rect(bar_x, bar_y, bar_width, 30, GRAY)
    
    # Filled portion (max 200 öre)
    max_price = 200
    filled_width = min(int((price_ore / max_price) * (bar_width - 4)), bar_width - 4)
    tft.fill_rect(bar_x + 2, bar_y + 2, filled_width, 26, price_color)
    
    print(f"Display updated: {price_ore} öre/kWh")

# Main
def main():
    print("=== Starting Tibber Display ===")
    
    try:
        init_display()
        
        if not connect_wifi():
            print("Cannot continue without WiFi")
            return
        
        # Main loop
        last_update = 0
        
        while True:
            current_time = time.time()
            
            # Update every 5 minutes
            if current_time - last_update > 300 or last_update == 0:
                price = get_tibber_price()
                draw_price(price)
                last_update = current_time
            
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("Stopped by user")
    except Exception as e:
        print(f"ERROR: {e}")
        if tft:
            tft.fill(BLACK)
            tft.text(font, "ERROR", 70, 100, RED)

if __name__ == "__main__":
    main()
