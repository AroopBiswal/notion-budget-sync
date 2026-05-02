"""Configuration: env vars and merchant categorization rules."""
import os
from dotenv import load_dotenv

load_dotenv()

# Plaid
PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID")
PLAID_SECRET = os.getenv("PLAID_SECRET")
PLAID_ENV = os.getenv("PLAID_ENV", "development")
PLAID_ACCESS_TOKEN = os.getenv("PLAID_ACCESS_TOKEN")

# Notion
NOTION_TOKEN = os.getenv("NOTION_TOKEN")

# Behavior
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "7"))

# Notion category names (must match the page titles in your Categories database)
CATEGORIES = ["Food", "Travel", "Fun", "Fixed", "Transportation", "Health", "Miscellaneous"]
FALLBACK_CATEGORY = "Miscellaneous"

# Merchant -> Category rules (substring match, case-insensitive)
# Add/edit these as you see new merchants in your Misc bucket
MERCHANT_RULES = {
    # Food / groceries / restaurants
    "trader joe": "Food",
    "whole foods": "Food",
    "safeway": "Food",
    "instacart": "Food",
    "doordash": "Food",
    "ubereats": "Food",
    "uber eats": "Food",
    "grubhub": "Food",
    "chipotle": "Food",
    "sweetgreen": "Food",
    "starbucks": "Food",
    "blue bottle": "Food",
    "philz": "Food",
    "tst*": "Food",  # Toast POS prefix, usually restaurants

    # Transportation
    "uber": "Transportation",  # note: "uber eats" matched above first
    "lyft": "Transportation",
    "caltrain": "Transportation",
    "clipper": "Transportation",
    "bart": "Transportation",
    "shell oil": "Transportation",
    "chevron": "Transportation",
    "76 ": "Transportation",
    "parking": "Transportation",

    # Fixed (rent, utilities, subscriptions you consider fixed)
    "pg&e": "Fixed",
    "pge": "Fixed",
    "comcast": "Fixed",
    "xfinity": "Fixed",
    "verizon": "Fixed",
    "t-mobile": "Fixed",
    "tmobile": "Fixed",
    "att ": "Fixed",
    "rent ": "Fixed",

    # Travel
    "united airlines": "Travel",
    "delta air": "Travel",
    "southwest": "Travel",
    "alaska air": "Travel",
    "american airlines": "Travel",
    "airbnb": "Travel",
    "marriott": "Travel",
    "hilton": "Travel",
    "hotels.com": "Travel",
    "expedia": "Travel",
    "booking.com": "Travel",

    # Health
    "cvs": "Health",
    "walgreens": "Health",
    "one medical": "Health",
    "kaiser": "Health",
    "rite aid": "Health",

    # Fun
    "spotify": "Fun",
    "netflix": "Fun",
    "hulu": "Fun",
    "amc theatres": "Fun",
    "ticketmaster": "Fun",
    "stubhub": "Fun",
    "axs.com": "Fun",
    "steam": "Fun",
    "playstation": "Fun",
}
