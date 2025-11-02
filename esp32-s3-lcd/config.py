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
