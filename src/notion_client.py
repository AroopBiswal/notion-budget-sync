"""Write normalized transactions to a user-provided Notion database."""
import logging
import time
from typing import Dict, List

from notion_client import Client

from .config import NOTION_TOKEN

log = logging.getLogger(__name__)

REQUIRED_PROPS = {
    "Name": "title",
    "Date": "date",
    "Amount": "number",
    "Category": "select",
    "TxnId": "rich_text",
}


def get_client() -> Client:
    return Client(auth=NOTION_TOKEN)


def extract_database_id(url_or_id: str) -> str:
    """Accept a full Notion URL or raw ID and return the 32-char hex database ID."""
    clean = url_or_id.split("?")[0].rstrip("/")
    segment = clean.split("/")[-1]
    # IDs appear after the last hyphen in the slug, or are the whole segment
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
    categories: List[str],
    rate_limit: float = 0.34,
) -> int:
    """Insert transactions as new Notion pages. Returns count written."""
    written = 0
    for txn, category in zip(txns, categories):
        notion.pages.create(
            parent={"database_id": database_id},
            properties={
                "Name": {"title": [{"text": {"content": txn["merchant"]}}]},
                "Date": {"date": {"start": txn["date"]}},
                "Amount": {"number": txn["amount"]},
                "Category": {"select": {"name": category}},
                "TxnId": {"rich_text": [{"text": {"content": txn["id"]}}]},
            },
        )
        written += 1
        time.sleep(rate_limit)  # stay under Notion's ~3 req/s limit
    return written
