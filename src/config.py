"""Environment variables and merchant categorization rules."""
import os
from dotenv import load_dotenv

load_dotenv()

# LLM
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_CATEGORIZATION = os.getenv("LLM_CATEGORIZATION", "false").lower() == "true"

# Notion
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# Category list (must match Select options in your Notion database)
CATEGORIES = ["Food", "Travel", "Fun", "Fixed", "Transportation", "Health", "Miscellaneous"]
FALLBACK_CATEGORY = "Miscellaneous"

# Merchant -> Category rules (substring match, case-insensitive, first match wins)
MERCHANT_RULES = {
    # Food / groceries / restaurants
    "trader joe": "Food",
    "whole foods": "Food",
    "safeway": "Food",
    "instacart": "Food",
    "doordash": "Food",
    "uber eats": "Food",
    "ubereats": "Food",
    "grubhub": "Food",
    "chipotle": "Food",
    "sweetgreen": "Food",
    "starbucks": "Food",
    "blue bottle": "Food",
    "philz": "Food",
    "tst*": "Food",

    # Transportation (uber eats matched above, so plain uber catches rides)
    "uber": "Transportation",
    "lyft": "Transportation",
    "caltrain": "Transportation",
    "clipper": "Transportation",
    "bart": "Transportation",
    "shell oil": "Transportation",
    "chevron": "Transportation",
    "76 ": "Transportation",
    "parking": "Transportation",

    # Fixed (subscriptions, utilities, rent)
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
