"""Write normalized transactions to a user-provided Notion database."""
import logging
import re
import time
from typing import Dict, List, Optional

from notion_client import Client

from .config import NOTION_TOKEN

log = logging.getLogger(__name__)

REQUIRED_PROPS = {
    "Name": "title",
    "Date": "date",
    "Amount": "number",
    "Category": "relation",
    "TxnId": "rich_text",
}


def get_client() -> Client:
    return Client(auth=NOTION_TOKEN)


def extract_database_id(url_or_id: str) -> str:
    """Accept a full Notion URL or raw ID and return the 32-char hex database ID."""
    clean = url_or_id.split("?")[0].rstrip("/")
    segment = clean.split("/")[-1]
    raw = segment.split("-")[-1].replace("-", "")
    if len(raw) == 32:
        return raw
    raw2 = segment.replace("-", "")
    return raw2[:32] if len(raw2) >= 32 else url_or_id.replace("-", "")


def validate_schema(notion: Client, database_id: str) -> None:
    """Raise RuntimeError with an actionable message if the DB schema is wrong."""
    db = notion.databases.retrieve(database_id=database_id)
    props = db.get("properties", {})

    errors = []
    for name, expected_type in REQUIRED_PROPS.items():
        if name not in props:
            errors.append(f"Missing property '{name}' (expected type: {expected_type})")
        elif props[name].get("type") != expected_type:
            actual = props[name].get("type")
            errors.append(f"Property '{name}' is type '{actual}', expected '{expected_type}'")

    if errors:
        raise RuntimeError(
            "Notion database schema validation failed:\n"
            + "\n".join(f"  - {e}" for e in errors)
            + "\n\nFix: run 'python -m scripts.init_notion <page_id>' or duplicate the template."
        )


def get_categories_db_id(notion: Client, database_id: str) -> str:
    """Discover the Categories database ID from the Category relation property."""
    db = notion.databases.retrieve(database_id=database_id)
    prop = db.get("properties", {}).get("Category", {})
    if prop.get("type") != "relation":
        raise RuntimeError(
            "The 'Category' property is not a relation. "
            "Duplicate the Notion template or run init_notion.py to set up the correct schema."
        )
    return prop["relation"]["database_id"]


def fetch_categories(notion: Client, categories_db_id: str) -> Dict[str, str]:
    """Return {category_name: page_id} for all pages in the Categories database."""
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


def _strip_prefix(name: str) -> str:
    """Strip leading emoji and whitespace from a category name for fuzzy matching."""
    return re.sub(r"^[\U0001F000-\U0001FFFF☀-➿\s]+", "", name).strip().lower()


def resolve_category(name: str, category_map: Dict[str, str]) -> Optional[str]:
    """Return the Notion page ID for a category, matching by emoji-stripped name if needed."""
    if name in category_map:
        return category_map[name]
    norm = _strip_prefix(name)
    for cat_name, page_id in category_map.items():
        if _strip_prefix(cat_name) == norm:
            return page_id
    # Fall back to Miscellaneous
    for cat_name, page_id in category_map.items():
        if "miscellaneous" in _strip_prefix(cat_name):
            return page_id
    return None


def existing_txn_ids(notion: Client, database_id: str) -> set:
    """Return all TxnId values already present in the database."""
    ids: set = set()
    cursor = None
    while True:
        kwargs: Dict = {"database_id": database_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = notion.databases.query(**kwargs)
        for page in resp.get("results", []):
            prop = page.get("properties", {}).get("TxnId")
            if prop:
                text = "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))
                if text:
                    ids.add(text)
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return ids


def add_transactions(
    notion: Client,
    database_id: str,
    txns: List[Dict],
    category_page_ids: List[str],
    rate_limit: float = 0.34,
) -> int:
    """Insert transactions as new Notion pages. Returns count written."""
    written = 0
    for txn, cat_page_id in zip(txns, category_page_ids):
        notion.pages.create(
            parent={"database_id": database_id},
            properties={
                "Name": {"title": [{"text": {"content": txn["merchant"]}}]},
                "Date": {"date": {"start": txn["date"]}},
                "Amount": {"number": txn["amount"]},
                "Category": {"relation": [{"id": cat_page_id}]},
                "TxnId": {"rich_text": [{"text": {"content": txn["id"]}}]},
            },
        )
        written += 1
        time.sleep(rate_limit)  # stay under Notion's ~3 req/s limit
    return written
