# config.py - Configuration for Tibber Energy Display
WIFI_SSID = suchvalue
WIFI_PASSWORD = suchvalue

# Tibber API
TIBBER_API_TOKEN = suchvalue # Get from https://developer.tibber.com/settings/access-token
TIBBER_API_URL = "https://api.tibber.com/v1-beta/gql"

# Display pins (from our successful probe)
DISPLAY_DC = 8
DISPLAY_RST = 12
DISPLAY_CS = 9
DISPLAY_SCK = 10
DISPLAY_MOSI = 11
DISPLAY_BL = 40
DISPLAY_SPI_ID = 1
DISPLAY_WIDTH = 240
DISPLAY_HEIGHT = 240

# Update intervals (seconds)
PRICE_UPDATE_INTERVAL = 300  # 5 minutes
POWER_UPDATE_INTERVAL = 10   # 10 seconds (for real-time power)

# Best window: cheapest N consecutive hours from now onwards
BEST_WINDOW_HOURS = 1

# Price thresholds in öre/kWh
PRICE_GREEN_MAX = 50    # below this = green
PRICE_YELLOW_MAX = 100  # below this = yellow, above = red
PRICE_BAR_MAX = 200     # öre/kWh that fills the bar completely

# --- Verdict service (LAN) ---------------------------------------------------
# When True the board asks the verdict service on Home Assistant instead of
# computing from Tibber itself. The service knows things the board cannot:
# live household power, the month's peak budget, and the effekttariff. It also
# means the decision logic can change without reflashing.
#
# Set False, or simply take the service down, to fall back to the direct-Tibber
# path below — the board does that automatically on any error or stale reading,
# so a bad deploy cannot leave you with a blank display.
USE_VERDICT_SERVICE = True
VERDICT_URL = "http://homeassistant.local:8099/verdict"
VERDICT_TIMEOUT = 5
