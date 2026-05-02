"""Categorize a merchant name using rules, falling back to Miscellaneous."""
from .config import MERCHANT_RULES, FALLBACK_CATEGORY


def categorize(merchant_name: str) -> str:
    """Return the category for a given merchant name.

    Uses substring matching (case-insensitive) against MERCHANT_RULES.
    Returns FALLBACK_CATEGORY if no rule matches.
    """
    if not merchant_name:
        return FALLBACK_CATEGORY

    name_lower = merchant_name.lower()
    for keyword, category in MERCHANT_RULES.items():
        if keyword in name_lower:
            return category

    return FALLBACK_CATEGORY
