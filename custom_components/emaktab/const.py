"""Constants for the eMaktab integration."""

DOMAIN = "emaktab"

# Platforms
PLATFORMS = ["sensor", "button"]

# Configuration keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_PERSON_ID = "person_id"
CONF_SCHOOL_ID = "school_id"
CONF_GROUP_ID = "group_id"
CONF_SCAN_INTERVAL = "scan_interval"

# URLs
LOGIN_URL = "https://login.emaktab.uz/login"
BASE_URL = "https://emaktab.uz"
USERFEED_URL = "https://emaktab.uz/userfeed"
API_BASE_URL = "https://emaktab.uz/api"

# Cookies
COOKIE_AUTH = "UZDnevnikAuth_a"
COOKIE_SESSION = "session_uuid"

# Defaults
DEFAULT_SCAN_INTERVAL = 3600  # seconds
REQUEST_TIMEOUT = 30  # seconds

# Headers
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
