"""Constants for the Hong Kong Towngas integration."""

DOMAIN = "towngas_hk"

CONF_ACCOUNT_NO = "account_no"
CONF_CSRF_TOKEN = "csrf_token"
CONF_BILLING_DATE = "billing_date"
CONF_NEXT_REFRESH = "next_refresh"
CONF_LAST_REFRESH = "last_refresh"
CONF_CACHED_DATA = "cached_data"

BASE_URL = "https://eservice.towngas.com"
LOGIN_PAGE = f"{BASE_URL}/en/Home/Index"
AUTH_PAGE = f"{BASE_URL}/en/billingUsage/Authentication"
LOGIN_API = f"{BASE_URL}/EAccount/Login/SignIn"
GENERATE_OTP_API = f"{BASE_URL}/EAccount/Login/GenerateVerifyCode"
ACCOUNT_API = f"{BASE_URL}/Common/GetHostedTGAccountAsync"
METER_API = f"{BASE_URL}/Common/GetMeterReadingInfoForChat"
BILLING_API = f"{BASE_URL}/EBilling/GetEBillingInfo"
NOTICE_API = f"{BASE_URL}/NewsNotices/GetNewsNoticeAsyncNew"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/144.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 10
# Refresh interval — 1 month (30 days). Meter readings are monthly.
# For testing, change to 5 (minutes).
SCAN_INTERVAL_MINUTES = 60 * 24 * 30  # 30 days

# Gas meter conversion factor
# Source: https://www.towngas.com/en/Household/Customer-Services/Tariff
# "Each unit registered by the gas meter represents that town gas
#  with a heat value of 48 MJ has been consumed"
UNITS_TO_MJ = 48

# Tariff constants – effective since 1 August 2024
# Source: https://www.towngas.com/en/Household/Customer-Services/Tariff
#
# Monthly Initial Charge: HK$20
#   "If the customer's gas charge is less than the monthly initial charge,
#    the monthly initial charge will be levied."
BASIC_CHARGE = 20.0
#
# Monthly Maintenance Charge: HK$10
#   "Covers labour costs for fully-qualified, registered gas technicians
#    to undertake maintenance and repair, on-demand inspections and a
#    regular safety inspection on an 18-month cycle."
MAINTENANCE_FEE = 10.0

# Tiered gas charges (cents per MJ)
# Each tuple is (upper_bound_mj, price_cents_per_mj).
# Tiers are cumulative: first tier covers MJ 0–500, second covers 501–2500, etc.
# Last tier uses inf to cover everything above 257,500 MJ.
TARIFF_TIERS = [
    (500,   28.55),   # First 500 MJ
    (2000,  28.45),   # Next 2,000 MJ (cumulative 501–2,500)
    (5000,  28.41),   # Next 5,000 MJ (cumulative 2,501–7,500)
    (10000, 28.31),   # Next 10,000 MJ (cumulative 7,501–17,500)
    (15000, 28.21),   # Next 15,000 MJ (cumulative 17,501–32,500)
    (25000, 28.08),   # Next 25,000 MJ (cumulative 32,501–57,500)
    (50000, 27.98),   # Next 50,000 MJ (cumulative 57,501–107,500)
    (50000, 27.89),   # Next 50,000 MJ (cumulative 107,501–157,500)
    (50000, 27.79),   # Next 50,000 MJ (cumulative 157,501–207,500)
    (50000, 27.70),   # Next 50,000 MJ (cumulative 207,501–257,500)
    (float("inf"), 27.60),  # Over 257,500 MJ
]

# Fuel Cost Adjustment – variable, published monthly by Towngas
# "For every complete multiple of HK$1 by which the effective feedstock
#  cost rises above (or falls below) HK$1,420/kL naphtha, the charge
#  increases (or decreases) by 0.004¢ per MJ."
# This value is set via an input_number helper; default used if helper missing.
DEFAULT_FUEL_ADJUSTMENT_RATE = 4.52  # cents per MJ
FUEL_RATE_ENTITY = "input_number.towngas_hk_{account}_fuel_adjust_rate"
