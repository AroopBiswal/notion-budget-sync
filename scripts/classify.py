"""Classify unclassified expenses in Notion using Claude Haiku with tool use.

Fetches categories dynamically from Notion at runtime, so any category names
or emoji prefixes you use in Notion are respected automatically.

Usage:
  python -m scripts.classify
  python -m scripts.classify --dry-run
"""
import argparse
import os
import sys
import time
from typing import Dict, List, Optional, Tuple

import anthropic
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
EXPENSES_DB_ID = os.getenv("NOTION_DATABASE_ID")
MODEL = "claude-haiku-4-5-20251001"
BATCH_SIZE = 25

# Descriptions injected into the prompt so the LLM knows what each category means.
# Keys are matched case-insensitively against the category name with emoji stripped.
DESCRIPTIONS = {
    "food": "groceries, restaurants, coffee shops, food delivery",
    "transportation": "Uber, Lyft, gas, parking, public transit",
    "travel": "flights, hotels, Airbnb, vacation expenses",
    "fixed": "rent, utilities, phone bills, recurring subscriptions",
    "health": "pharmacy, doctor visits, gym, medical expenses",
    "fun": "entertainment, movies, concerts, games, streaming services",
    "miscellaneous": "anything that doesn't fit the above categories",
}


# ── Notion helpers ────────────────────────────────────────────────────────────

def get_categories_db_id(notion: Client, expenses_db_id: str) -> str:
    db = notion.databases.retrieve(database_id=expenses_db_id)
    prop = db.get("properties", {}).get("Category", {})
    if prop.get("type") != "relation":
        raise RuntimeError(
            "The 'Category' property on the Expenses database is not a relation. "
            "Make sure you duplicated the Notion template correctly."
        )
    return prop["relation"]["database_id"]


def fetch_categories(notion: Client, categories_db_id: str) -> Dict[str, str]:
    """Return {category_name: page_id} fetched live from Notion."""
    mapping: Dict[str, str] = {}
    cursor = None
    while True:
        kwargs: Dict = {"database_id": categories_db_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = notion.databases.query(**kwargs)
        for page in resp.get("results", []):
            for prop in page.get("properties", {}).values():
                if prop.get("type") == "title":
                    name = "".join(t["plain_text"] for t in prop.get("title", []))
                    if name:
                        mapping[name.strip()] = page["id"]
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return mapping


def fetch_unclassified(notion: Client, expenses_db_id: str) -> List[Dict]:
    """Return expense rows where the Category relation is empty."""
    expenses = []
    cursor = None
    while True:
        kwargs: Dict = {
            "database_id": expenses_db_id,
            "page_size": 100,
            "filter": {"property": "Category", "relation": {"is_empty": True}},
        }
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = notion.databases.query(**kwargs)
        for page in resp.get("results", []):
            props = page.get("properties", {})
            name = ""
            amount = 0.0
            for prop_name, prop in props.items():
                if prop.get("type") == "title":
                    name = "".join(t["plain_text"] for t in prop.get("title", []))
                elif prop_name == "Amount" and prop.get("type") == "number":
                    amount = prop.get("number") or 0.0
            if name:
                expenses.append({"page_id": page["id"], "name": name.strip(), "amount": amount})
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return expenses


def update_category(notion: Client, page_id: str, category_page_id: str) -> None:
    notion.pages.update(
        page_id=page_id,
        properties={"Category": {"relation": [{"id": category_page_id}]}},
    )


# ── LLM ───────────────────────────────────────────────────────────────────────

def _description_for(cat_name: str) -> str:
    """Return a description for a category name by stripping emoji and matching."""
    import re
    clean = re.sub(r"^[\U0001F000-\U0001FFFF☀-➿\s]+", "", cat_name).strip().lower()
    return DESCRIPTIONS.get(clean, "")


def classify_batch(
    client: anthropic.Anthropic,
    expenses: List[Dict],
    category_names: List[str],
) -> List[Tuple[int, str]]:
    """Classify a batch. Returns list of (1-based index, category_name)."""

    cats_text = "Categories:\n" + "".join(
        f"- {name}" + (f": {desc}" if (desc := _description_for(name)) else "") + "\n"
        for name in category_names
    )
    txns_text = "\nTransactions:\n" + "".join(
        f"{i + 1}. {exp['name']} | ${exp['amount']:.2f}\n"
        for i, exp in enumerate(expenses)
    )

    tool = {
        "name": "classify_expenses",
        "description": "Classify each transaction into exactly one category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "classifications": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer", "description": "1-based transaction index"},
                            "category": {"type": "string", "enum": category_names},
                        },
                        "required": ["index", "category"],
                    },
                }
            },
            "required": ["classifications"],
        },
    }

    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        tools=[tool],
        tool_choice={"type": "tool", "name": "classify_expenses"},
        system=(
            "You are an expense classifier. "
            "Classify each purchase into exactly one of the provided categories. "
            "Use Miscellaneous for anything ambiguous or that doesn't fit."
        ),
        messages=[{"role": "user", "content": cats_text + txns_text}],
    )

    for block in resp.content:
        if block.type == "tool_use" and block.name == "classify_expenses":
            return [(c["index"], c["category"]) for c in block.input.get("classifications", [])]
    return []


def _find_fallback(category_map: Dict[str, str]) -> Optional[str]:
    """Return page ID for the Miscellaneous-equivalent category."""
    import re
    for name, pid in category_map.items():
        clean = re.sub(r"^[\U0001F000-\U0001FFFF☀-➿\s]+", "", name).strip().lower()
        if "miscellaneous" in clean:
            return pid
    return None


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Classify unclassified Notion expenses with Claude.")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to Notion")
    args = parser.parse_args()

    if not NOTION_TOKEN:
        print("ERROR: Set NOTION_TOKEN in .env")
        return 1
    if not ANTHROPIC_API_KEY:
        print("ERROR: Set ANTHROPIC_API_KEY in .env (required for classification)")
        return 1
    if not EXPENSES_DB_ID:
        print("ERROR: Set NOTION_DATABASE_ID in .env")
        return 1

    notion = Client(auth=NOTION_TOKEN)
    ai = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    print("Fetching categories from Notion...")
    cats_db_id = get_categories_db_id(notion, EXPENSES_DB_ID)
    category_map = fetch_categories(notion, cats_db_id)
    if not category_map:
        print("ERROR: No categories found in the Categories database.")
        return 1
    category_names = list(category_map.keys())
    print(f"  {len(category_names)} categories: {', '.join(category_names)}")

    fallback_id = _find_fallback(category_map)

    print("Fetching unclassified expenses...")
    expenses = fetch_unclassified(notion, EXPENSES_DB_ID)
    if not expenses:
        print("  Nothing to classify.")
        return 0
    print(f"  {len(expenses)} unclassified expenses found.")

    # Classify in batches
    updates: List[Tuple[str, str, str]] = []  # (page_id, cat_page_id, cat_name)

    for start in range(0, len(expenses), BATCH_SIZE):
        batch = expenses[start : start + BATCH_SIZE]
        batch_num = start // BATCH_SIZE + 1
        total = (len(expenses) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"Classifying batch {batch_num}/{total} ({len(batch)} transactions)...")

        classifications = classify_batch(ai, batch, category_names)
        classified = {c[0] for c in classifications}

        # Warn about any missing indices and fall back to Miscellaneous
        for i in range(1, len(batch) + 1):
            if i not in classified:
                print(f"  WARNING: no classification returned for #{i} ({batch[i-1]['name']})")
                if fallback_id:
                    classifications.append((i, next(k for k, v in category_map.items() if v == fallback_id)))

        for idx, cat_name in classifications:
            if idx < 1 or idx > len(batch):
                continue
            exp = batch[idx - 1]
            cat_page_id = category_map.get(cat_name)
            if not cat_page_id:
                print(f"  WARNING: category '{cat_name}' not found in Notion - skipping")
                continue
            updates.append((exp["page_id"], cat_page_id, cat_name))

    if not updates:
        print("Nothing to write.")
        return 0

    # Tally by category for summary
    tally: Dict[str, int] = {}
    for _, _, name in updates:
        tally[name] = tally.get(name, 0) + 1

    if args.dry_run:
        print(f"\n[dry-run] Would classify {len(updates)} expenses:")
        for name, count in sorted(tally.items(), key=lambda x: -x[1]):
            print(f"  {name}: {count}")
    else:
        print(f"\nWriting {len(updates)} classifications to Notion...")
        for page_id, cat_page_id, _ in updates:
            update_category(notion, page_id, cat_page_id)
            time.sleep(0.34)
        summary = ", ".join(f"{n} ({c})" for n, c in sorted(tally.items(), key=lambda x: -x[1]))
        print(f"Done. Classified {len(updates)} expenses: {summary}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
