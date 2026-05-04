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

    When LLM_CATEGORIZATION is true, all transactions are sent to the LLM.
    When false, falls back to rule-based matching only.
    """
    effective_cats = valid_categories if valid_categories is not None else CATEGORIES

    if LLM_CATEGORIZATION:
        categories: List[Optional[str]] = [None] * len(txns)
        _llm_fill(txns, categories, list(range(len(txns))), effective_cats)
        return [c or FALLBACK_CATEGORY for c in categories]

    return [categorize(t["merchant"]) for t in txns]


def _llm_fill(txns: List[Dict], categories: List, indices: List[int], valid_categories: List[str]) -> None:
    from .llm.factory import get_provider
    provider = get_provider()
    batch_size = 20

    for start in range(0, len(indices), batch_size):
        batch = indices[start : start + batch_size]
        merchants = [txns[i]["merchant"] for i in batch]
        n = len(merchants)

        cats = ",".join(valid_categories)
        system = "You are a transaction categorizer. Reply with JSON only."
        user = (
            f"Categories: {cats}\n"
            + "\n".join(f"{j+1}.{m}" for j, m in enumerate(merchants))
            + f'\nReturn: {{"categories":[...{n} items]}}'
        )

        try:
            result = provider.complete_json(system, user)
            llm_cats = result.get("categories", [])
            for j, idx in enumerate(batch):
                raw = llm_cats[j] if j < len(llm_cats) else FALLBACK_CATEGORY
                categories[idx] = raw if raw in valid_categories else FALLBACK_CATEGORY
        except Exception as exc:
            log.warning("LLM categorization failed for batch: %s", exc)
