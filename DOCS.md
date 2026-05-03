# notion-budget-sync - Full Documentation

## Table of contents

1. [Detailed setup](#detailed-setup)
2. [Web UI](#web-ui)
3. [Format profiles](#format-profiles)
4. [CLI reference](#cli-reference)
5. [Categorization](#categorization)
6. [Architecture](#architecture)
7. [FAQ](#faq)
8. [Contributing](#contributing)

---

## Detailed setup

### Notion

#### Step 1: Create an integration

1. Go to [notion.so/my-integrations](https://notion.so/my-integrations)
2. Click **+ New integration**, name it (e.g., "notion-budget-sync"), select your workspace
3. Copy the **Internal Integration Secret** into `NOTION_TOKEN` in your `.env`

#### Step 2: Set up the database

**Option A: Duplicate the template**

Duplicate the [Notion template](https://wood-sedum-f63.notion.site/May-template-355e7c7c7bb4800dbc10e8078713e24e) into your workspace. The template has the correct schema pre-configured.

**Option B: Run the init script**

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

#### Step 3: Share the database

Open the database in Notion, click **...** (top right), go to **Connections**, search for your integration name, and confirm.

#### Step 4: Get the database URL

Paste the full URL from your browser into the app. It looks like:
```
https://notion.so/yourworkspace/Budget-<database_id>
```
The app extracts the ID automatically.

---

### LLM

notion-budget-sync calls an LLM once per new file format to identify which columns map to date, merchant, and amount. After a profile is saved, no further LLM calls are made for that format.

| Provider | Env var | Recommended model | Cost estimate |
|---|---|---|---|
| Anthropic | `ANTHROPIC_API_KEY` | `claude-haiku-4-5-20251001` | ~$0.001 per new profile |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o-mini` | ~$0.001 per new profile |

If both keys are present, Anthropic is used. Get keys at [console.anthropic.com](https://console.anthropic.com) or [platform.openai.com](https://platform.openai.com).

---

## Web UI

```bash
python app.py
# Open http://localhost:5000
```

The UI is a single dark-mode page with three inputs and two action buttons.

**Notion Database URL** - paste the full URL from your browser.

**Format Profile** - a dropdown of saved profiles plus **Auto-detect** (default). Select a saved profile to skip LLM inference entirely. Use Auto-detect the first time you import from a new bank.

**File upload** - drag and drop or click to browse. Supported: `.csv`, `.tsv`, `.xlsx`, `.xls`, `.json`.

**Dry Run** - shows a preview table (date, merchant, amount, category) without writing to Notion.

**Sync** - writes new transactions and shows a summary (added / skipped).

### Saving a new profile

When Auto-detect encounters a new format, the LLM infers the column mapping and a save prompt appears:

```
New format detected.
Save as: [Chase Sapphire CSV     ] [Save]
```

Give it a recognizable name. If a profile with that name already exists, the new one is saved as "Chase Sapphire CSV 2", "Chase Sapphire CSV 3", etc.

Click the **gear icon** next to the dropdown to open the profile manager where you can delete any saved profile.

---

## Format profiles

Profiles are stored in `.schema_cache/profiles.json`. Each profile has six mapping fields:

| Field | Description |
|---|---|
| `date_col` | Column containing the transaction date |
| `merchant_col` | Column containing the merchant or description |
| `amount_col` | Column containing the dollar amount |
| `category_col` | Category column, if one exists (or null) |
| `txn_id_col` | Unique transaction ID column, if one exists (or null) |
| `amount_sign` | `"positive_is_charge"` or `"negative_is_charge"` |

You can edit `profiles.json` directly to correct a field.

**Deduplication:** if `txn_id_col` is set, that column's value is used as `TxnId`. Otherwise the ID is generated from `sha1(date + merchant + amount)[:16]`. A row is skipped if its `TxnId` is already in Notion.

---

## CLI reference

```bash
# Sync (auto-detect format)
python -m src.main path/to/transactions.csv

# Dry run
python -m src.main path/to/transactions.csv --dry-run

# Use a named profile
python -m src.main path/to/transactions.csv --format "Chase Sapphire CSV"

# Auto-detect and save the profile in one step
python -m src.main path/to/transactions.csv --save-format "Chase Sapphire CSV"

# List all saved profiles
python -m src.main --list-formats

# Delete a profile
python -m src.main --delete-format "Chase Sapphire CSV"
```

Profiles saved via the CLI are visible in the web UI dropdown and vice versa.

### Dry run output example

```
Format: "Chase Sapphire CSV" (saved profile)
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

---

## Categorization

Transactions are categorized using `MERCHANT_RULES` in `src/config.py`. Each entry maps a merchant name substring (case-insensitive) to one of the seven categories. First match wins.

```python
MERCHANT_RULES = {
    "trader joe": "Food",
    "whole foods": "Food",
    "my gym": "Health",  # add your merchants here
}
```

If no rule matches, the transaction goes into **Miscellaneous**.

**Optional LLM categorization:** set `LLM_CATEGORIZATION=true` in `.env` to have the LLM categorize unmatched transactions. They are batched (up to 20 per call) and sent with the list of valid categories. Off by default.

---

## Architecture

```
notion-budget-sync/
├── app.py                      # Flask web app entry point
├── static/
│   ├── style.css               # dark mode styles (CSS custom properties)
│   └── app.js                  # file upload, sync, profile management UI
├── templates/
│   └── index.html              # single-page app shell
├── src/
│   ├── config.py               # env vars, MERCHANT_RULES, category list
│   ├── categorizer.py          # rules-first matching, optional LLM fallback
│   ├── notion_client.py        # validates schema, dedupes, writes rows
│   ├── main.py                 # CLI entry point + shared pipeline logic
│   ├── llm/
│   │   ├── base.py             # LLMProvider ABC
│   │   ├── anthropic_provider.py
│   │   ├── openai_provider.py
│   │   └── factory.py          # picks provider from env
│   └── ingestion/
│       ├── reader.py           # reads CSV/XLSX/TSV/JSON
│       ├── schema_mapper.py    # LLM inference + profile persistence
│       └── normalizer.py       # applies mapping, generates TxnIds
├── scripts/
│   └── init_notion.py          # one-time: creates the Notion database
└── .schema_cache/
    ├── profiles.json           # named format profiles
    └── <hash>.json             # raw cached mappings
```

**Data flow (web and CLI share the same pipeline):**

```
File
  -> reader.py          parses into (headers, rows)
  -> schema_mapper.py   loads profile OR calls LLM and caches result
  -> normalizer.py      produces [{id, date, merchant, amount}]
  -> categorizer.py     assigns a category to each row
  -> notion_client.py   dedupes against existing TxnIds, writes new rows
```

---

## FAQ

**"Notion database schema validation failed"**

1. Confirm you used the template or ran `init_notion.py`
2. Property names are case-sensitive: `Name`, `Date`, `Amount`, `Category`, `Month`, `TxnId`
3. `Category` must be a **Select** property
4. `Month` must be a **Formula** property

**"No LLM provider configured"**

Set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in `.env`. Only needed when creating a new profile - once saved, the LLM is not called again for that format.

**"The column mapping looks wrong"**

Edit `.schema_cache/profiles.json` directly and correct the field. Or delete the profile and let it re-detect.

**"Transactions keep appearing as duplicates"**

Your bank may normalize merchant names differently each export, causing the generated TxnId to change. Fix: set `txn_id_col` in the profile to your bank's native transaction ID column.

**"Two banks with identical column headers"**

Save them as separate named profiles and always select the correct one. Auto-detect matches by header hash, which collides if the headers are identical.

**"I get a 401 from Notion"**

Your `NOTION_TOKEN` is wrong, or the integration has not been shared with the database. Re-check Notion setup Step 3.

**"File upload does nothing"**

Check the terminal running `app.py` for error output.

---

## Contributing

### Adding a new LLM provider

1. Create `src/llm/yourprovider_provider.py` implementing the `LLMProvider` ABC from `src/llm/base.py`
2. The only required method: `complete_json(self, system: str, user: str) -> dict`
3. Update `src/llm/factory.py` to detect your key env var and return an instance
4. Add the SDK to `requirements.txt`

### Adding a new file reader

1. Add a branch to `src/ingestion/reader.py` for your extension
2. Return `(headers: list[str], rows: list[dict])` - same contract as existing readers

### Adding categorization rules

Edit `MERCHANT_RULES` in `src/config.py`. Put more specific strings before less specific ones (`"uber eats"` before `"uber"`).

### Customizing the UI

`static/style.css` uses CSS custom properties for the color scheme. All values are defined as variables on `:root` at the top of the file.
