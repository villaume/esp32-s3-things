import network
import time
import gc
import math
import gc9a01
from machine import Pin, SPI
import vga1_16x32 as font

# Smaller font for the labels. vga1_16x16 is generated from vga1_16x32 by
# tools/make_small_font.py (the big font is that face doubled vertically).
#
# This must be a real imported module: the GC9A01 driver's text() is C code
# that calls mp_obj_module_get_globals() on the font argument, so handing it a
# class or any other object crashes the board with LoadProhibited. If the file
# is missing we fall back to the big font and a reduced layout.
font_small = font
for _name in ("vga1_8x16", "vga1_16x16"):
    try:
        font_small = __import__(_name)
        break
    except ImportError:
        pass
HAS_SMALL = font_small.HEIGHT < font.HEIGHT

# Import config
try:
    from config import *
    print("Config loaded")
except Exception as e:
    print(f"Config error: {e}")

# Config fallbacks, so an older config.py on the device still works
try:
    BEST_WINDOW_HOURS
except NameError:
    BEST_WINDOW_HOURS = 1

try:
    PRICE_GREEN_MAX
except NameError:
    PRICE_GREEN_MAX = 50   # öre/kWh

try:
    PRICE_YELLOW_MAX
except NameError:
    PRICE_YELLOW_MAX = 100  # öre/kWh

try:
    PRICE_BAR_MAX
except NameError:
    PRICE_BAR_MAX = 200     # öre/kWh = full bar

try:
    PRICE_UPDATE_INTERVAL
except NameError:
    PRICE_UPDATE_INTERVAL = 300  # seconds

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

# Get current price + today/tomorrow hourly prices from Tibber
def get_tibber_prices():
    print("Fetching Tibber prices...")
    query = """
    {
      viewer {
        homes {
          currentSubscription {
            priceInfo {
              current { total startsAt }
              today { total startsAt }
              tomorrow { total startsAt }
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

    response = None
    try:
        import urequests
        response = urequests.post(
            TIBBER_API_URL,
            headers=headers,
            json={'query': query}
        )

        data = response.json()
        response.close()
        response = None
        gc.collect()

        info = data['data']['viewer']['homes'][0]['currentSubscription']['priceInfo']
        current = info['current']
        hours = list(info.get('today') or [])
        hours.extend(info.get('tomorrow') or [])

        # NB: MicroPython's f-strings cannot contain quotes inside {}, so use %
        print("Price: %s SEK/kWh, %d hours known" % (current['total'], len(hours)))
        return current, hours

    except Exception as e:
        print(f"Tibber API error: {e}")
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
        return None, []

# startsAt looks like "2026-08-04T14:00:00.000+02:00"
def hour_of(entry):
    return int(entry['startsAt'][11:13])

# Cheapest run of BEST_WINDOW_HOURS consecutive hours, from now onwards.
# Tibber's own current.startsAt is used as the clock, so the board needs no NTP.
def find_best_window(current, hours):
    if not current or not hours:
        return None

    now = current['startsAt']
    # ISO strings with the same UTC offset sort chronologically
    upcoming = [h for h in hours if h['startsAt'] >= now]
    n = BEST_WINDOW_HOURS
    if len(upcoming) < n:
        return None

    best_i = 0
    best_sum = None
    for i in range(len(upcoming) - n + 1):
        total = 0.0
        for j in range(i, i + n):
            total += upcoming[j]['total']
        if best_sum is None or total < best_sum:
            best_sum = total
            best_i = i

    start = upcoming[best_i]
    return {
        'start_hour': hour_of(start),
        'end_hour': (hour_of(start) + n) % 24,
        'avg_ore': int(round(best_sum / n * 100)),
        'is_now': start['startsAt'] == now,
        'hours_away': best_i,
    }

def price_color(ore):
    if ore < PRICE_GREEN_MAX:
        return GREEN
    elif ore < PRICE_YELLOW_MAX:
        return YELLOW
    return RED

def center_text(f, s, y, color):
    x = (DISPLAY_WIDTH - len(s) * f.WIDTH) // 2
    if x < 0:
        x = 0
    tft.text(f, s, x, y, color)

# The panel is round, so the usable width shrinks towards the top and bottom.
# Returns how many characters of font f actually fit on a line drawn at y.
def fit_chars(f, y):
    r = DISPLAY_WIDTH // 2
    dy = max(abs(y - r), abs(y + f.HEIGHT - r))
    if dy >= r:
        return 0
    return int(2 * math.sqrt(r * r - dy * dy)) // f.WIDTH

# Draw the first candidate that fits inside the bezel; candidates are ordered
# most-verbose first, so a long price or offset degrades instead of clipping.
def center_best(f, candidates, y, color):
    n = fit_chars(f, y)
    for s in candidates:
        if len(s) <= n:
            center_text(f, s, y, color)
            return
    center_text(f, candidates[-1], y, color)

# Draw price + best window on display
def draw_price(current, window):
    tft.fill(BLACK)

    if current is None:
        tft.text(font, "API Error", 40, 100, RED)
        return

    price_ore = int(current['total'] * 100)  # Convert to öre
    color = price_color(price_ore)

    # Header. The panel is round, so the title has to sit low enough that the
    # bezel does not eat the first and last characters.
    tft.fill_rect(0, 0, DISPLAY_WIDTH, 46, BLUE)
    center_text(font, "ELPRIS", 12, WHITE)

    if HAS_SMALL:
        y_price, y_unit, y_bar = 52, 88, 110
        bar_h = 18
        y_label, y_window, y_wprice = 134, 154, 190
    else:
        y_price, y_unit, y_bar = 54, None, 94
        bar_h = 18
        y_label, y_window, y_wprice = None, 120, 158

    # Large current price
    center_text(font, str(price_ore), y_price, color)
    if y_unit is not None:
        center_text(font_small, "ore/kWh", y_unit, WHITE)

    # Relative price bar
    bar_width = 180
    bar_x = (DISPLAY_WIDTH - bar_width) // 2
    tft.rect(bar_x, y_bar, bar_width, bar_h, GRAY)
    filled = min(int((price_ore / PRICE_BAR_MAX) * (bar_width - 4)), bar_width - 4)
    if filled > 0:
        tft.fill_rect(bar_x + 2, y_bar + 2, filled, bar_h - 4, color)

    # Best window
    if window is None:
        center_text(font_small if HAS_SMALL else font, "no data", y_window, GRAY)
        print(f"Display updated: {price_ore} ore/kWh, no window")
        return

    wcolor = price_color(window['avg_ore'])

    if y_label is not None:
        center_text(font_small, "BILLIGAST NU" if window['is_now'] else "BILLIGAST",
                    y_label, GRAY)

    center_text(font, "%02d-%02d" % (window['start_hour'], window['end_hour']),
                y_window, wcolor)

    ore, away = window['avg_ore'], window['hours_away']
    if window['is_now']:
        tail = ("%d ore NU" % ore, "%do NU" % ore, "NU")
    else:
        tail = ("%d ore +%dh" % (ore, away), "%do +%dh" % (ore, away),
                "+%dh" % away)
    center_best(font_small, tail, y_wprice, WHITE)

    print("Display updated: %d ore/kWh, best %02d-%02d @ %d ore"
          % (price_ore, window['start_hour'], window['end_hour'],
             window['avg_ore']))

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

            if current_time - last_update > PRICE_UPDATE_INTERVAL or last_update == 0:
                current, hours = get_tibber_prices()
                window = find_best_window(current, hours)
                draw_price(current, window)
                last_update = current_time
                hours = None
                gc.collect()

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
