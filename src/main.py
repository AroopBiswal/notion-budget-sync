"""CLI entry point and shared pipeline logic."""
import argparse
import logging
import sys
from typing import Dict, List, Optional

from .config import NOTION_DATABASE_ID
from .ingestion.reader import read_file
from .ingestion.schema_mapper import (
    delete_profile,
    find_cached_by_headers,
    get_profile,
    infer_mapping,
    load_profiles,
    save_profile,
)
from .ingestion.normalizer import normalize
from .categorizer import categorize_batch
from .notion_client import (
    add_transactions,
    existing_txn_ids,
    extract_database_id,
    get_client,
    validate_schema,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def run_pipeline(
    file_path: str,
    database_url: str,
    format_name: Optional[str] = None,
    save_as: Optional[str] = None,
    dry_run: bool = False,
) -> Dict:
    """Core pipeline shared by the web UI and CLI.

    Returns a summary dict with keys:
      read, normalized, new, skipped, written, is_new_format, mapping, preview
    """
    headers, rows = read_file(file_path)

    # Resolve schema mapping
    is_new_format = False
    if format_name:
        mapping = get_profile(format_name)
        if not mapping:
            raise RuntimeError(
                f"No saved profile named '{format_name}'. "
                "Run --list-formats to see available profiles."
            )
        resolved_name = format_name
    else:
        resolved_name, mapping = find_cached_by_headers(headers)
        if mapping is None:
            log.info("New format detected - calling LLM to infer column mapping...")
            mapping = infer_mapping(headers, rows)
            is_new_format = True
            log.info("Schema inferred.")
        else:
            log.info('Format: "%s" (cached profile)', resolved_name)

    if save_as:
        actual_name = save_profile(save_as, mapping, headers)
        if actual_name != save_as:
            log.info('Profile saved as "%s" (name already existed).', actual_name)
        else:
            log.info('Profile saved as "%s".', actual_name)

    # Normalize
    txns = normalize(rows, mapping)
    log.info("Transactions read: %d  normalized: %d", len(rows), len(txns))

    # Notion dedupe
    notion = get_client()
    db_id = extract_database_id(database_url)
    validate_schema(notion, db_id)
    seen = existing_txn_ids(notion, db_id)

    new_txns = [t for t in txns if t["id"] not in seen]
    skipped = len(txns) - len(new_txns)
    log.info("Already in Notion: %d  New this run: %d", skipped, len(new_txns))

    categories: List[str] = categorize_batch(new_txns) if new_txns else []

    written = 0
    if not dry_run and new_txns:
        written = add_transactions(notion, db_id, new_txns, categories)
        log.info("Done. Wrote %d transactions.", written)

    preview = [
        {"date": t["date"], "merchant": t["merchant"], "amount": t["amount"], "category": c}
        for t, c in zip(new_txns[:50], categories[:50])
    ]

    return {
        "read": len(rows),
        "normalized": len(txns),
        "new": len(new_txns),
        "skipped": skipped,
        "written": written,
        "is_new_format": is_new_format,
        "mapping": mapping,
        "preview": preview,
    }


def _cli_dry_run_table(preview: List[Dict]) -> None:
    print(f"\n{'Date':<12} {'Merchant':<36} {'Amount':>9}  Category")
    print("-" * 72)
    for row in preview:
        print(f"{row['date']:<12} {row['merchant'][:35]:<36} ${row['amount']:>8.2f}  {row['category']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync bank transaction exports to Notion."
    )
    parser.add_argument("file", nargs="?", help="Path to transaction file")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to Notion")
    parser.add_argument("--format", dest="format_name", metavar="NAME", help="Use a saved format profile")
    parser.add_argument("--save-format", dest="save_format", metavar="NAME", help="Save detected format under this name")
    parser.add_argument("--list-formats", action="store_true", help="List all saved profiles and exit")
    parser.add_argument("--delete-format", dest="delete_format", metavar="NAME", help="Delete a saved profile and exit")
    args = parser.parse_args()

    if args.list_formats:
        profiles = load_profiles()
        if not profiles:
            print("No saved format profiles.")
        else:
            print("Saved format profiles:")
            for name, p in profiles.items():
                preview = ", ".join(str(h) for h in p.get("headers_preview", [])[:3])
                print(f"  {name:<30}  [{preview} ...]  saved {p.get('saved', '?')}")
        return 0

    if args.delete_format:
        if delete_profile(args.delete_format):
            print(f'Deleted profile "{args.delete_format}".')
        else:
            print(f'Profile "{args.delete_format}" not found.')
        return 0

    if not args.file:
        parser.error("A file path is required (or use --list-formats).")

    db_url = NOTION_DATABASE_ID
    if not db_url:
        print("ERROR: Set NOTION_DATABASE_ID in .env")
        return 1

    try:
        result = run_pipeline(
            file_path=args.file,
            database_url=db_url,
            format_name=args.format_name,
            save_as=args.save_format,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        log.error("%s", exc)
        return 1

    if args.dry_run:
        print(f"\nTransactions read:   {result['read']}")
        print(f"After normalization: {result['normalized']}")
        print(f"Already in Notion:   {result['skipped']}")
        print(f"New this run:        {result['new']}")
        if result["preview"]:
            _cli_dry_run_table(result["preview"])
            if result["new"] > len(result["preview"]):
                print(f"  ... and {result['new'] - len(result['preview'])} more")
        print("\n[dry-run] No changes written to Notion.")

    if result["is_new_format"] and not args.save_format:
        print("\nNew format detected. Save it for future runs with:")
        print(f'  python -m src.main {args.file} --save-format "Your Bank CSV"')

    return 0


if __name__ == "__main__":
    sys.exit(main())
