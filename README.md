# notion-budget-sync

Import transactions from any bank export file (CSV, XLSX, and more) into your Notion budget database. No bank API credentials, no OAuth, no subscriptions. You export the file your bank already gives you; notion-budget-sync does the rest.

---

## Why this exists

Every bank lets you download a CSV. Not every bank supports third-party API integrations. And even when they do, those integrations break when banks update their flows, require paid API tiers, or simply don't support your institution.

notion-budget-sync takes the file you already have and syncs it to Notion. It uses an LLM exactly once per file format to figure out which columns correspond to date, merchant, and amount - then caches that mapping locally. From then on, every sync runs fully deterministically with no LLM calls and no ongoing API costs.

## Who it's for

- Anyone who exports transactions from their bank or credit card website and wants them in Notion
- People whose bank is not supported by Plaid, Teller, or similar services
- Anyone who prefers a local tool with no persistent connection to their bank

---

## Quick start

Requires Python 3.11+ and either an Anthropic or OpenAI API key.

**1. Clone and install**
```bash
git clone https://github.com/you/notion-budget-sync
cd notion-budget-sync
pip install -r requirements.txt
```

**2. Set up your Notion database** (duplicate the [template](#notion-template) or run the init script)
```bash
python -m scripts.init_notion <parent_page_id>
```

**3. Configure `.env`**
```bash
cp .env.example .env
# Fill in NOTION_TOKEN, NOTION_DATABASE_ID, and one LLM key
```

**4. Preview with a dry run**
```bash
python -m src.main path/to/transactions.csv --dry-run
```

**5. Sync**
```bash
python -m src.main path/to/transactions.csv
```

---

## Detailed setup

### Notion

#### Step 1: Create an integration

1. Go to [notion.so/my-integrations](https://notion.so/my-integrations)
2. Click **+ New integration**, name it (e.g., "notion-budget-sync"), select your workspace
3. Copy the **Internal Integration Secret** - this becomes `NOTION_TOKEN` in your `.env`

#### Step 2: Set up the database

**Option A: Duplicate the template**

Duplicate the [notion-budget-sync Notion template](#) into your workspace. The template has the correct schema pre-configured. *(Template link coming soon - use Option B in the meantime.)*

**Option B: Run the init script (recommended)**

```bash
python -m scripts.init_notion <parent_page_id>
```

`<parent_page_id>` is the ID of the Notion page that should contain the new database. Find it in the page URL: `notion.so/Your-Page-Title-<page_id>`. The script prints the new database ID when it finishes.

**Option C: Create manually**

Create a full-page database with these exact property names and types:

| Property | Type | Notes |
|---|---|---|
| `Name` | Title | Merchant or transaction description |
| `Date` | Date | Transaction date |
| `Amount` | Number | Format: US Dollar |
| `Category` | Select | Options: Food, Travel, Fun, Fixed, Transportation, Health, Miscellaneous |
| `Month` | Formula | `formatDate(prop("Date"), "MMMM YYYY")` - gives "May 2026" for grouping |
| `TxnId` | Text | Deduplication key - hide this column in your Notion view |

#### Step 3: Share the database with your integration

Open the database in Notion, click **...** (top right), go to **Connections**, search for your integration name, and confirm.

#### Step 4: Get the database ID

Open the database as a full page. The URL looks like:
```
https://notion.so/yourworkspace/Budget-<database_id>
```
Copy the 32-character ID at the end. That is your `NOTION_DATABASE_ID`.

---

### LLM

notion-budget-sync uses an LLM once per file format to identify which columns map to date, merchant, and amount. The result is saved in `.schema_cache/`. After the first run for a given format, no further LLM calls are made for schema discovery.

**Supported providers:**

| Provider | Env var | Recommended model | Cost estimate |
|---|---|---|---|
| Anthropic | `ANTHROPIC_API_KEY` | `claude-haiku-4-5-20251001` | ~$0.001 per schema discovery |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o-mini` | ~$0.001 per schema discovery |

If both keys are present, Anthropic is used. Set only the one you want.

- Anthropic key: [console.anthropic.com](https://console.anthropic.com)
- OpenAI key: [platform.openai.com](https://platform.openai.com)

---

### Categorization

Transactions are categorized using a rules dictionary in `src/config.py`. Each entry maps a merchant name substring (case-insensitive) to one of the seven categories.

**To add your own rules:**

Open `src/config.py` and edit `MERCHANT_RULES`:

```python
MERCHANT_RULES = {
    "trader joe": "Food",
    "whole foods": "Food",
    "my gym": "Health",  # add your merchants here
    ...
}
```

Rules are checked in order. The first match wins. If no rule matches, the transaction goes into **Miscellaneous**.

**Optional: LLM-powered categorization**

Set `LLM_CATEGORIZATION=true` in `.env` to have the LLM categorize anything that doesn't match a rule. Unmatched transactions are batched (up to 20 at a time) and sent to the LLM with the list of valid categories. This produces better results than falling back to Miscellaneous, at a small additional cost per run. It is off by default.

---

## How to run

### Basic sync

```bash
python -m src.main path/to/transactions.csv
```

Supported file formats: `.csv`, `.tsv`, `.xlsx`, `.xls`, `.json`

### Dry run

Preview what would be written without touching Notion:

```bash
python -m src.main path/to/transactions.csv --dry-run
```

Example output:
```
Schema: using cached mapping (headers hash: a3f8c2d1)
Transactions read:  47
Already in Notion:  31
New this run:       16

Date         Merchant                   Amount    Category
2026-04-28   WHOLE FOODS MARKET         $54.32    Food
2026-04-27   LYFT *RIDE                 $18.50    Transportation
2026-04-26   NETFLIX.COM                $15.49    Fun
... (13 more)

[dry-run] No changes written to Notion.
```

### Clearing the schema cache

If the column mapping looks wrong (e.g., merchant and amount are swapped), delete the cache and re-run:

```bash
rm .schema_cache/*.json
```

The next run re-infers the schema. You can also manually edit a cached `.json` file if you only need to correct one field.

---

## Architecture

```
notion-budget-sync/
├── src/
│   ├── config.py              # env vars, MERCHANT_RULES, category list
│   ├── categorizer.py         # rules-first matching, optional LLM fallback
│   ├── notion_client.py       # validates schema, dedupes, writes rows
│   ├── main.py                # CLI entry point (argparse)
│   ├── llm/
│   │   ├── base.py            # LLMProvider ABC: complete_json(system, user) -> dict
│   │   ├── anthropic_provider.py
│   │   ├── openai_provider.py
│   │   └── factory.py         # reads env, returns the right provider
│   └── ingestion/
│       ├── reader.py          # reads CSV/XLSX/TSV/JSON, returns (headers, rows)
│       ├── schema_mapper.py   # LLM call + .schema_cache/ persistence
│       └── normalizer.py      # applies mapping, normalizes amounts, generates TxnIds
├── scripts/
│   └── init_notion.py         # one-time: creates the Notion database
├── .schema_cache/             # gitignored - one JSON file per file format seen
├── .env.example
└── requirements.txt
```

**Data flow:**

```
File on disk
  -> reader.py          reads into (headers, rows)
  -> schema_mapper.py   identifies date/merchant/amount columns (cached after first run)
  -> normalizer.py      produces [{id, date, merchant, amount}]
  -> categorizer.py     assigns a category to each row
  -> notion_client.py   dedupes against existing TxnIds, writes new rows
```

**Deduplication:** If your export includes a transaction ID column, that value is used as `TxnId`. If not, the ID is generated from `sha1(date + merchant + amount)[:16]`. A row is skipped if its `TxnId` is already present in Notion.

---

## FAQ

**"Notion database schema validation failed"**

notion-budget-sync checks your database schema before writing. If this fails:
1. Confirm you used the template or ran `init_notion.py`
2. Property names are case-sensitive. They must be exactly: `Name`, `Date`, `Amount`, `Category`, `Month`, `TxnId`
3. `Category` must be a **Select** property, not a text field
4. `Month` must be a **Formula** property

**"No LLM provider configured"**

Set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in your `.env`. You only need this for the first run per file format, but it must be present until the schema is cached.

**"The schema inferred looks wrong"**

Delete `.schema_cache/*.json` and re-run. If the LLM consistently maps columns incorrectly, open an issue with a sanitized sample of your file headers and the incorrect mapping. You can also edit the cached JSON directly - it is a plain JSON file with six fields (`date_col`, `merchant_col`, `amount_col`, `category_col`, `txn_id_col`, `amount_sign`).

**"Transactions keep appearing as duplicates"**

This usually means the `TxnId` is being generated differently across runs - for example, your bank normalizes merchant names differently each time you export. Check the `TxnId` values in Notion and compare them to what the current export produces. The fix is to add your bank's native transaction ID column: edit the cached `.schema_cache/*.json` and set `txn_id_col` to the correct column name from your file.

**"My file is not in a supported format"**

Open an issue. The reader module is straightforward to extend (see Contributing below).

**"I get a 401 from Notion"**

Your `NOTION_TOKEN` is wrong, or the integration has not been connected to the database. Re-check Step 3 of the Notion setup: open the database, go to **Connections**, and confirm your integration appears in the list.

---

## Contributing

### Adding a new LLM provider

1. Create `src/llm/yourprovider_provider.py`
2. Implement the `LLMProvider` ABC from `src/llm/base.py`. The only required method is:
   ```python
   def complete_json(self, system: str, user: str) -> dict: ...
   ```
3. Update `src/llm/factory.py` to detect your provider's API key env var and return an instance
4. Add the SDK to `requirements.txt`

The `complete_json` contract: given a system prompt and a user message, return a parsed Python dict. Your implementation is responsible for enforcing JSON output (via the provider's JSON mode or a prompt suffix).

### Adding a new file reader

1. Add a branch to `src/ingestion/reader.py` for your file extension
2. Return `(headers: list[str], rows: list[dict])` - the same contract as existing readers
3. No changes are needed elsewhere in the pipeline

### Adding categorization rules

Edit `MERCHANT_RULES` in `src/config.py` and open a PR. Rules are case-insensitive substring matches. Put more specific strings before less specific ones (e.g., `"uber eats"` before `"uber"`).
