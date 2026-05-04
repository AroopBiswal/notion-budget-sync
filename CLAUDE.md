# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## GitHub

**Always ask for confirmation before pushing to GitHub.** The user wants to test features locally before any commit lands on the remote. Never run `git push` without explicit approval.

## Running the app

```bash
python app.py          # web UI at http://localhost:5000
python -m src.main path/to/transactions.csv --dry-run   # CLI dry run
python -m src.main path/to/transactions.csv             # CLI sync
```

**Environment:** copy `.env.example` to `.env` and fill in `NOTION_TOKEN` plus `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`. The Flask server caches env vars at import time — restart it after changing `.env`.

## Architecture

The web UI (`app.py`) and CLI (`src/main.py`) share one pipeline: `run_pipeline()` in `src/main.py`.

**Data flow:**
```
File → reader.py (parse) → schema_mapper.py (map columns) → normalizer.py (normalize)
     → categorizer.py (assign category) → notion_client.py (dedupe + write)
```

**Key behaviors to know:**
- `schema_mapper.py` checks `.schema_cache/profiles.json` for a matching header hash before calling the LLM. If a saved profile matches, the LLM is never called.
- `amount_sign` in a profile is detected programmatically (majority-vote on positive vs negative amounts), not by the LLM — this avoids mis-inference on mixed statements.
- `normalizer.py` drops rows where `amount <= 0` after sign normalization. This is intentional (payments/refunds are skipped). If many rows are unexpectedly filtered, the `amount_sign` in the profile is likely wrong.
- Deduplication uses `TxnId`: either the bank's native ID column (`txn_id_col` in the profile) or `sha1(date|merchant|amount)[:16]`. The web UI stats show "In Notion" (already deduplicated) separately from "Filtered" (dropped during normalization).

**LLM providers** (`src/llm/`): `factory.py` picks Anthropic if `ANTHROPIC_API_KEY` is set, otherwise OpenAI. Both implement the `LLMProvider` ABC (`complete_json(system, user) -> dict`).

**Notion schema** — the Expenses database requires exactly these properties: `Name` (title), `Date` (date), `Amount` (number), `Category` (relation to a Categories database), `TxnId` (rich_text).

**Saved databases** (Notion URLs) are stored in `.schema_cache/db_urls.json`. **Format profiles** are stored in `.schema_cache/profiles.json`. Both are managed through the web UI.

## Extending

- **New LLM provider:** implement `complete_json` from `src/llm/base.py`, update `src/llm/factory.py`.
- **New file format:** add a branch to `src/ingestion/reader.py`, return `(headers: list[str], rows: list[dict])`.
- **New merchant rules:** edit `MERCHANT_RULES` in `src/config.py` — put specific substrings before generic ones (`"uber eats"` before `"uber"`).
- **UI color scheme:** all colors are CSS custom properties on `:root` in `static/style.css`.
