# notion-budget-sync

Import transactions from any bank export (CSV, XLSX, and more) into your Notion budget database.

Available as a **web UI**, a **macOS Dock app**, or a **CLI**. All three use the same pipeline.

Context: I track my spending on Notion but it's time consuming to manually add all my purchases one by one. So I made this app to automate it.

---

<img width="719" height="646" alt="image" src="https://github.com/user-attachments/assets/b98e4822-5e7b-481b-ac74-5e2f7096d48a" />

---

## Features

- Drop in any bank export (CSV, XLSX, TSV, JSON) — the LLM auto-detects the column format on first use and caches it for future runs
- LLM categorizes each transaction into your Notion categories
- Dry-run preview with per-row checkboxes and category dropdowns before syncing
- Month filter to sync only a specific month
- Saves Notion database URLs and format profiles for quick re-use

---

## How it works

1. Export a transaction file from your bank (any format)
2. Drop it into the web UI, paste your Notion page URL, click **Run**
3. Review the preview — adjust categories, deselect rows, filter by month
4. Click **Confirm Sync** to push to Notion
5. The first time you use a new file format, the LLM maps the columns and saves a **format profile** (e.g. "Chase Sapphire CSV") — every run after that skips the LLM entirely

---

## Setup

### 1. Prerequisites

- Python 3.11+
- An [Anthropic](https://console.anthropic.com) or [OpenAI](https://platform.openai.com) API key (for format detection and categorization)

### 2. Clone and install

```bash
git clone https://github.com/AroopBiswal/notion-budget-sync
cd notion-budget-sync
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in:

```
ANTHROPIC_API_KEY=sk-ant-...      # get from console.anthropic.com
NOTION_TOKEN=ntn_...              # get from notion.so/my-integrations (step 4)
LLM_CATEGORIZATION=true
```

### 4. Notion setup

**Create an integration:**
1. Go to [notion.so/my-integrations](https://notion.so/my-integrations) → **New integration**
2. Give it a name (e.g. "Budget Sync"), select your workspace, click **Save**
3. Copy the **Internal Integration Token** → paste into `NOTION_TOKEN` in `.env`

**Set up the database:**
- Duplicate the [Notion template](https://wood-sedum-f63.notion.site/May-template-355e7c7c7bb4800dbc10e8078713e24e) into your workspace, **or**
- Run `python -m scripts.init_notion <parent_page_id>` to create the databases automatically

The page must contain two databases: **Expenses** and **Categories**.

**Share with your integration:**
Open the page in Notion → click **...** (top right) → **Connections** → select your integration.

---

## Running the app

### Web UI (terminal)

```bash
python app.py
# opens at http://localhost:5000
```

### macOS Dock app

Build a native `.app` that launches from your Dock with a single click:

```bash
bash scripts/desktop-build.sh
bash scripts/desktop-install.sh
```

This installs `Notion Budget Sync.app` to `~/Applications/App It/`. Drag that folder to the right side of your Dock once as a Stack.

**First launch:** click the app — macOS will ask for Documents folder access (required since the project lives in `~/Documents`). Click **Allow**. Every launch after that is instant.

**Rebuild** after moving the repo: `bash scripts/desktop-build.sh && bash scripts/desktop-install.sh`

### CLI

```bash
python -m src.main path/to/transactions.csv --dry-run   # preview
python -m src.main path/to/transactions.csv             # sync
```

---

## Using the web UI

1. **Select a Notion database** — paste your Notion page URL or pick a saved one from the dropdown
2. **Select a transaction file** — drag and drop, browse, or pick from the `transactions/` folder shortcut
3. **Click Run** — shows a preview table with categories, amounts, and checkboxes
4. Adjust categories or deselect rows you don't want, filter by month if needed
5. **Click Confirm Sync** — pushes only the checked rows to Notion

Place your bank exports in the `transactions/` folder for quick access from the file picker.
