"""Constants for the Hong Kong Towngas integration."""

DOMAIN = "towngas_hk"

CONF_ACCOUNT_NO = "account_no"

BASE_URL = "https://eservice.towngas.com"
LOGIN_PAGE = f"{BASE_URL}/en/Home/Index"
LOGIN_API = f"{BASE_URL}/EAccount/Login/SignIn"
ACCOUNT_API = f"{BASE_URL}/Common/GetHostedTGAccountAsync"
METER_API = f"{BASE_URL}/Common/GetMeterReadingInfoForChat"
BILLING_API = f"{BASE_URL}/EBilling/GetEBillingInfo"
NOTICE_API = f"{BASE_URL}/NewsNotices/GetNewsNoticeAsyncNew"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/144.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 30
SCAN_INTERVAL_HOURS = 1

# configuration
CONF_FUEL_ADJUSTMENT_RATE = "fuel_adjustment_rate"

# default helper value (cents per MJ)
DEFAULT_FUEL_ADJUSTMENT_RATE = 4.52
# entity ID template for the input_number helper
FUEL_RATE_ENTITY = "input_number.towngas_hk_{account}_fuel_adjust_rate"

# fixed monthly fees (used by tariff calculation)
BASIC_CHARGE = 20.0
MAINTENANCE_FEE = 10.0
