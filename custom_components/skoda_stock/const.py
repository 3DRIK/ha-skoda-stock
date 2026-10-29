"""Constants for Škoda Stock."""
DOMAIN = "skoda_stock"
VERSION = "1.0.1"

CONF_MODELS = "models"
CONF_INTERVAL_HOURS = "interval_hours"
CONF_MAX_PRICE = "max_price"
CONF_MAX_KM = "max_km"
CONF_INCLUDE_DEMO = "include_demo"
CONF_LINK_TEMPLATE = "link_template"

DEFAULT_MODELS = ["BIBQ", "BIBT"]
DEFAULT_INTERVAL_HOURS = 3
MODEL_OPTIONS = [
    {"value": "BIBQ", "label": "Elroq (BIBQ)"},
    {"value": "BIBT", "label": "Epiq (BIBT)"},
]

API_URL = "https://www.skoda-auto.sk/apps/stock/654/sk-SK/api/search"
LIST_URL = "https://www.skoda-auto.sk/apps/stock/carSearch"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/143.0 Safari/537.36"
)
PAGE_DELAY = 1.5   # seconds between page requests
MAX_PAGES = 60

CARD_URL = "/skoda_stock/skoda-stock-card.js"
CARD_FILE = "skoda-stock-card.js"
STORAGE_VERSION = 1

EVT_NEW = "skoda_stock_new_car"
EVT_DROP = "skoda_stock_price_drop"
EVT_RISE = "skoda_stock_price_increase"
EVT_RESERVED = "skoda_stock_reserved"
EVT_UNRESERVED = "skoda_stock_unreserved"
EVT_REMOVED = "skoda_stock_car_removed"
EVT_UPDATED = "skoda_stock_updated"

API_DETAIL_URL = "https://www.skoda-auto.sk/apps/stock/654/sk-SK/api/getCarDetail"
DETAIL_DELAY = 1.5        # seconds between detail requests
DETAIL_RETRY_HOURS = 6    # retry a failed/empty detail fetch after this long
DETAIL_NEW_CAP = 15       # new cars whose detail is fetched before their alert is sent
