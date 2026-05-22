# notion-budget-sync



Import transactions from any bank export (CSV, XLSX, and more) into your Notion budget database.

Available as a **web UI** or a **CLI**. Both use the same pipeline.

Context: I track my spending on Notion but its time consuming to have to manually add all my purchases one by one. So I made this app to automate it.


<img width="719" height="646" alt="image" src="https://github.com/user-attachments/assets/b98e4822-5e7b-481b-ac74-5e2f7096d48a" />



# Features

## Transaction data to Notion

- Input: bring your own transaction data in whatever format your bank exports (CSV, XLSX, etc.)
- Output: data shows up in your Notion budget database, sorted into categories.
- An LLM detects your file format on the first run and caches the mapping for instant later runs.
- The same LLM can categorize unknown merchants, or you can let them fall into Miscellaneous.

## Automatic budget tracking via Plaid (coming soon)

- Input: connect your bank or credit card once through Plaid.
- Output: transactions sync to Notion automatically on a schedule.
- Removes the manual step from the workflow; same categorization and Notion output, without CSV download.

---

## How it works

1. Export a transaction file from your bank (any format)
2. Drop it into the web UI, paste your Notion database URL, click Sync
3. The first time you use a new file format, an LLM figures out the column mapping and saves it as a named **format profile** (e.g., "Chase Sapphire CSV")
4. Every run after that is free and deterministic - no LLM calls

---

## Quick start

Requires Python 3.11+ and an [Anthropic](https://console.anthropic.com) or [OpenAI](https://platform.openai.com) API key.

```bash
git clone https://github.com/AroopBiswal/notion-budget-sync
cd notion-budget-sync
pip install -r requirements.txt
cp .env.example .env   # fill in NOTION_TOKEN + one LLM key
python app.py          # open http://localhost:5000
```

Or use the CLI:
```bash
python -m src.main path/to/transactions.csv --dry-run
python -m src.main path/to/transactions.csv
```

---

## Notion setup

**1.** Create an integration at [notion.so/my-integrations](https://notion.so/my-integrations) and copy the token into `NOTION_TOKEN` in your `.env`.

**2.** Set up the database - pick one:
- Duplicate the [Notion template](https://wood-sedum-f63.notion.site/May-template-355e7c7c7bb4800dbc10e8078713e24e) into your workspace
- Or run `python -m scripts.init_notion <parent_page_id>` to create one automatically

**3.** Share the database with your integration: open it in Notion, click **...** -> **Connections** -> select your integration.
*** You can 

**4.** Paste the database URL into the app (it extracts the ID automatically).

---

## More details

See [DOCS.md](DOCS.md) for full setup instructions, format profile reference, CLI flags, architecture overview, FAQ, and contributing guidelines.
