"""One-time script: create the budget Notion database with the required schema.

Usage:
  python -m scripts.init_notion <parent_page_id>

The parent_page_id is the ID of the Notion page that should contain the new database.
Find it in the page URL: notion.so/Your-Page-Title-<page_id>
"""
import sys

from notion_client import Client

from src.config import CATEGORIES, NOTION_TOKEN


def create_database(parent_page_id: str) -> str:
    notion = Client(auth=NOTION_TOKEN)

    db = notion.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": "Budget"}}],
        properties={
            "Name": {"title": {}},
            "Date": {"date": {}},
            "Amount": {"number": {"format": "dollar"}},
            "Category": {
                "select": {
                    "options": [{"name": c} for c in CATEGORIES]
                }
            },
            "Month": {
                "formula": {
                    "expression": 'formatDate(prop("Date"), "MMMM YYYY")'
                }
            },
            "TxnId": {"rich_text": {}},
        },
    )
    return db["id"]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.init_notion <parent_page_id>")
        sys.exit(1)

    if not NOTION_TOKEN:
        print("ERROR: Set NOTION_TOKEN in .env first.")
        sys.exit(1)

    page_id = sys.argv[1]
    print(f"Creating database under page {page_id}...")
    db_id = create_database(page_id)

    print("\nDatabase created successfully.")
    print(f"Database ID: {db_id}")
    print("\nAdd this to your .env:")
    print(f"NOTION_DATABASE_ID={db_id}")
    print("\nThen share the database with your integration:")
    print("  Open the database -> ... -> Connections -> [your integration name]")
