"""One-time script: create the Expenses + Categories databases matching the template.

Usage:
  python -m scripts.init_notion <parent_page_id>

The parent_page_id is the ID of the Notion page that should contain both databases.
Find it in the page URL: notion.so/Your-Page-Title-<page_id>

Categories are created with emoji prefixes matching the template. You can rename or
add categories freely in Notion after setup - the tool fetches them dynamically at runtime.
"""
import sys

from notion_client import Client

from src.config import NOTION_TOKEN

# Default categories with emoji prefixes matching the published template.
# Edit these before running if you want different categories from the start.
DEFAULT_CATEGORIES = [
    "🤤 Food",
    "✈️ Travel",
    "💃 Fun",
    "🔧 Fixed",
    "🚗 Transportation",
    "❤️ Health",
    "✨ Miscellaneous",
]


def create_databases(parent_page_id: str) -> tuple:
    """Create the Categories database then the Expenses database with a relation to it."""
    notion = Client(auth=NOTION_TOKEN)

    # 1. Create the Categories database first (needed for the relation)
    print("  Creating Categories database...")
    cats_db = notion.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": "Categories"}}],
        properties={"Name": {"title": {}}},
    )
    cats_db_id = cats_db["id"]

    # 2. Populate categories as pages
    for cat_name in DEFAULT_CATEGORIES:
        notion.pages.create(
            parent={"database_id": cats_db_id},
            properties={"Name": {"title": [{"text": {"content": cat_name}}]}},
        )

    # 3. Create the Expenses database with a relation to Categories
    print("  Creating Expenses database...")
    expenses_db = notion.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": "Expenses"}}],
        properties={
            "Name": {"title": {}},
            "Date": {"date": {}},
            "Amount": {"number": {"format": "dollar"}},
            "Category": {
                "relation": {
                    "database_id": cats_db_id,
                    "single_property": {},
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
    expenses_db_id = expenses_db["id"]

    return expenses_db_id, cats_db_id


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.init_notion <parent_page_id>")
        sys.exit(1)

    if not NOTION_TOKEN:
        print("ERROR: Set NOTION_TOKEN in .env first.")
        sys.exit(1)

    page_id = sys.argv[1]
    print(f"Creating databases under page {page_id}...")

    expenses_id, cats_id = create_databases(page_id)

    print("\nDone.")
    print(f"  Expenses database ID: {expenses_id}")
    print(f"  Categories database ID: {cats_id}")
    print("\nAdd this to your .env:")
    print(f"  NOTION_DATABASE_ID={expenses_id}")
    print("\nThen share both databases with your integration:")
    print("  Open each database -> ... -> Connections -> [your integration name]")
