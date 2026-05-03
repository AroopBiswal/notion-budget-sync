"""Categorize transactions using rules, with optional LLM batch fallback."""
import logging
from typing import Dict, List, Optional

from .config import CATEGORIES, FALLBACK_CATEGORY, LLM_CATEGORIZATION, MERCHANT_RULES

log = logging.getLogger(__name__)


def categorize(merchant: str) -> str:
    """Return a category via case-insensitive substring matching against MERCHANT_RULES."""
    lower = merchant.lower()
    for keyword, category in MERCHANT_RULES.items():
        if keyword.lower() in lower:
            return category
    return FALLBACK_CATEGORY


def categorize_batch(txns: List[Dict], valid_categories: Optional[List[str]] = None) -> List[str]:
    """Return a category string for each transaction in txns (parallel list).

    valid_categories: the list fetched live from Notion. Falls back to config.CATEGORIES
    if not provided. Used to constrain the LLM fallback to categories that actually exist.
    """
    effective_cats = valid_categories if valid_categories is not None else CATEGORIES
    categories: List[Optional[str]] = []
    unmatched: List[int] = []

    for i, txn in enumerate(txns):
        cat = categorize(txn["merchant"])
        if cat == FALLBACK_CATEGORY and LLM_CATEGORIZATION:
            categories.append(None)
            unmatched.append(i)
        else:
            categories.append(cat)

    if unmatched:
        _llm_fill(txns, categories, unmatched, effective_cats)

    return [c or FALLBACK_CATEGORY for c in categories]


def _llm_fill(txns: List[Dict], categories: List, indices: List[int], valid_categories: List[str]) -> None:
    from .llm.factory import get_provider
    provider = get_provider()
    batch_size = 20

    for start in range(0, len(indices), batch_size):
        batch = indices[start : start + batch_size]
        merchants = [txns[i]["merchant"] for i in batch]
        n = len(merchants)

        system = "You are a budget categorization assistant. Reply with JSON only."
        user = (
            f"Categorize each merchant into exactly one of: {valid_categories}\n\n"
            + "\n".join(f"{j + 1}. {m}" for j, m in enumerate(merchants))
            + f'\n\nReturn: {{"categories": ["cat1", ...]}} with exactly {n} items.'
        )

        try:
            result = provider.complete_json(system, user)
            llm_cats = result.get("categories", [])
            for j, idx in enumerate(batch):
                raw = llm_cats[j] if j < len(llm_cats) else FALLBACK_CATEGORY
                categories[idx] = raw if raw in valid_categories else FALLBACK_CATEGORY
        except Exception as exc:
            log.warning("LLM categorization failed for batch: %s", exc)
