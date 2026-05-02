"""Entry point: fetch transactions, categorize, write to Notion."""
import logging
import sys
from datetime import datetime

from .config import LOOKBACK_DAYS, FALLBACK_CATEGORY
from .plaid_client import fetch_transactions
from .categorizer import categorize
from .notion_client import (
    _client as notion_client,
    find_month_page,
    resolve_databases,
    load_category_page_ids,
    ensure_plaid_id_property,
    existing_plaid_ids,
    add_transaction,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def main() -> int:
    log.info("Starting AMEX -> Notion sync")

    # 1. Fetch from Plaid
    log.info(f"Fetching transactions from Plaid (last {LOOKBACK_DAYS} days)")
    txns = fetch_transactions(LOOKBACK_DAYS)
    log.info(f"Fetched {len(txns)} settled transactions")
    if not txns:
        log.info("Nothing to do")
        return 0

    # 2. Find current month page in Notion
    notion = notion_client()
    month_page_id = find_month_page(notion)
    if not month_page_id:
        month_name = datetime.now().strftime("%B")
        log.error(f"No Notion page titled '{month_name}' found. Create it from your template and re-run.")
        return 1
    log.info(f"Found month page: {month_page_id}")

    # 3. Resolve transactions and categories databases
    dbs = resolve_databases(notion, month_page_id)
    transactions_db_id = dbs["transactions"]
    categories_db_id = dbs["categories"]

    # 4. Make sure PlaidId property exists for dedupe
    ensure_plaid_id_property(notion, transactions_db_id)

    # 5. Load existing IDs and category page mapping
    seen_ids = existing_plaid_ids(notion, transactions_db_id)
    category_pages = load_category_page_ids(notion, categories_db_id)
    log.info(f"Categories available: {sorted(category_pages.keys())}")
    if FALLBACK_CATEGORY not in category_pages:
        log.error(f"Fallback category '{FALLBACK_CATEGORY}' not found in Notion Categories DB")
        return 1

    # 6. Filter, categorize, write
    new_count = 0
    skipped_count = 0
    for txn in txns:
        if txn["id"] in seen_ids:
            skipped_count += 1
            continue
        category_name = categorize(txn["name"])
        # Defensive: if a rule maps to a category that doesn't exist in Notion, fall back
        if category_name not in category_pages:
            log.warning(f"Category '{category_name}' missing in Notion - using {FALLBACK_CATEGORY}")
            category_name = FALLBACK_CATEGORY
        category_page_id = category_pages[category_name]

        log.info(f"  + {txn['date']} {txn['name']} ${txn['amount']:.2f} -> {category_name}")
        add_transaction(notion, transactions_db_id, txn, category_page_id)
        new_count += 1

    log.info(f"Done. Added {new_count} new, skipped {skipped_count} duplicates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
