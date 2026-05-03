"""Notion client: find the current month page, resolve its databases, and write transactions.

Page layout assumed:
  - A page titled with the current month name (e.g., "April")
  - That page contains TWO inline child databases:
      1. Transactions table with columns: Date, Name, Category (relation), Amount
      2. A "Categories" database whose pages are titled "Food", "Travel", etc.
  - The Category property on the transactions DB is a RELATION to the Categories DB.

Dedupe strategy:
  We add a hidden text property "TellerId" to the transactions DB on first run if missing.
  Subsequent runs skip transactions whose TellerId is already present.
"""
from datetime import date
from typing import Dict, List, Optional

from notion_client import Client

from .config import NOTION_TOKEN

_TX_ID_PROP = "TellerId"


def _client() -> Client:
    return Client(auth=NOTION_TOKEN)


def _current_month_name() -> str:
    return date.today().strftime("%B")  # "April", "May", etc.


def find_month_page(notion: Client, month_name: Optional[str] = None) -> Optional[str]:
    """Find a page whose title matches the current month name. Returns page ID or None."""
    target = month_name or _current_month_name()
    results = notion.search(query=target, filter={"property": "object", "value": "page"})
    for page in results.get("results", []):
        # Check the page title
        title_prop = None
        props = page.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                title_prop = prop
                break
        if not title_prop:
            continue
        title_text = "".join(t.get("plain_text", "") for t in title_prop.get("title", []))
        if title_text.strip().lower() == target.lower():
            return page["id"]
    return None


def find_child_databases(notion: Client, page_id: str) -> List[Dict]:
    """Return all child_database blocks under a page, in order."""
    databases = []
    cursor = None
    while True:
        kwargs = {"block_id": page_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = notion.blocks.children.list(**kwargs)
        for block in resp.get("results", []):
            if block.get("type") == "child_database":
                databases.append(block)
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return databases


def resolve_databases(notion: Client, page_id: str) -> Dict[str, str]:
    """Identify which child database is transactions vs categories.

    We distinguish by inspecting the database schema:
      - Transactions DB has an "Amount" number property
      - Categories DB does not (or is the other one)
    """
    child_dbs = find_child_databases(notion, page_id)
    if len(child_dbs) < 2:
        raise RuntimeError(
            f"Expected 2 child databases on month page, found {len(child_dbs)}"
        )

    transactions_db_id = None
    categories_db_id = None

    for db_block in child_dbs:
        db_id = db_block["id"]
        db = notion.databases.retrieve(database_id=db_id)
        props = db.get("properties", {})
        has_amount = any(p.get("type") == "number" and name.lower() == "amount"
                         for name, p in props.items())
        if has_amount:
            transactions_db_id = db_id
        else:
            categories_db_id = db_id

    if not transactions_db_id or not categories_db_id:
        raise RuntimeError("Could not identify transactions and categories databases")

    return {"transactions": transactions_db_id, "categories": categories_db_id}


def load_category_page_ids(notion: Client, categories_db_id: str) -> Dict[str, str]:
    """Return {category_name: page_id} for all pages in the Categories database."""
    mapping = {}
    cursor = None
    while True:
        kwargs = {"database_id": categories_db_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = notion.databases.query(**kwargs)
        for page in resp.get("results", []):
            title = ""
            for prop in page.get("properties", {}).values():
                if prop.get("type") == "title":
                    title = "".join(t.get("plain_text", "") for t in prop.get("title", []))
                    break
            if title:
                mapping[title.strip()] = page["id"]
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return mapping


def ensure_tx_id_property(notion: Client, transactions_db_id: str) -> None:
    """Add a hidden 'TellerId' rich_text property to the transactions DB if missing."""
    db = notion.databases.retrieve(database_id=transactions_db_id)
    if _TX_ID_PROP in db.get("properties", {}):
        return
    notion.databases.update(
        database_id=transactions_db_id,
        properties={_TX_ID_PROP: {"rich_text": {}}},
    )


def existing_tx_ids(notion: Client, transactions_db_id: str) -> set:
    """Return the set of TellerId values already present in the transactions DB."""
    ids = set()
    cursor = None
    while True:
        kwargs = {"database_id": transactions_db_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = notion.databases.query(**kwargs)
        for page in resp.get("results", []):
            prop = page.get("properties", {}).get(_TX_ID_PROP)
            if not prop:
                continue
            text = "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))
            if text:
                ids.add(text)
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return ids


def _find_property_name(db: Dict, type_name: str, fallback_name: str) -> str:
    """Find the first property of given type, fall back to fallback_name."""
    for name, prop in db.get("properties", {}).items():
        if prop.get("type") == type_name:
            return name
    return fallback_name


def add_transaction(
    notion: Client,
    transactions_db_id: str,
    txn: Dict,
    category_page_id: str,
) -> None:
    """Create one row in the transactions database."""
    db = notion.databases.retrieve(database_id=transactions_db_id)
    props_schema = db.get("properties", {})

    # Resolve actual property names (in case capitalization differs)
    name_prop = _find_property_name(db, "title", "Name")
    date_prop = next((n for n, p in props_schema.items() if p.get("type") == "date"), "Date")
    amount_prop = next((n for n, p in props_schema.items() if p.get("type") == "number"), "Amount")
    category_prop = next((n for n, p in props_schema.items() if p.get("type") == "relation"), "Category")

    properties = {
        name_prop: {"title": [{"text": {"content": txn["name"]}}]},
        date_prop: {"date": {"start": txn["date"]}},
        amount_prop: {"number": txn["amount"]},
        category_prop: {"relation": [{"id": category_page_id}]},
        _TX_ID_PROP: {"rich_text": [{"text": {"content": txn["id"]}}]},
    }

    notion.pages.create(parent={"database_id": transactions_db_id}, properties=properties)
