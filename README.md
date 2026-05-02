# AMEX → Notion Budget Sync

Pulls AMEX transactions from Plaid, categorizes them with simple rules (with a Miscellaneous fallback), and writes them to your monthly Notion budget page. Runs daily on GitHub Actions.

## How it works

1. Plaid pulls the last 7 days of settled AMEX transactions
2. Each transaction is categorized via a substring-match rule list (`src/config.py` → `MERCHANT_RULES`). Anything that doesn't match goes to **Miscellaneous**.
3. The script finds the Notion page titled with the current month name (e.g., "April"), locates the two child databases inside it (transactions table and Categories), and adds new rows.
4. Dedupe is handled via a hidden `PlaidId` text property on each transaction row.

## One-time setup

### 1. Plaid

1. Sign up at https://dashboard.plaid.com
2. Note your `client_id` and the `Development` environment `secret`
3. Copy `.env.example` to `.env` and fill in `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV=development`
4. Run the link helper to get an access token:
   ```bash
   pip install -r requirements.txt
   python -m scripts.link_account
   ```
5. Open http://localhost:8000, click "Link AMEX", complete the OAuth flow with American Express
6. Copy the printed `access_token` into `.env` as `PLAID_ACCESS_TOKEN`

### 2. Notion

1. Create an integration: https://notion.so/my-integrations → copy the token
2. Open your monthly budget page in Notion → click "..." top right → Connections → add your integration. Repeat on the parent page if your monthly pages live under one.
3. Make sure the integration has access to **every** month page you'll use, or the parent that contains them all.
4. Add `NOTION_TOKEN` to `.env`

### 3. Local test

Make sure your current month's page exists in Notion (e.g., "May" if it's May), then run:

```bash
python -m src.main
```

You should see new transactions appear in the Notion table.

### 4. Deploy to GitHub Actions

1. Push this repo to GitHub (private)
2. Settings → Secrets and variables → Actions → add the same env vars as repo secrets:
   - `PLAID_CLIENT_ID`
   - `PLAID_SECRET`
   - `PLAID_ENV`
   - `PLAID_ACCESS_TOKEN`
   - `NOTION_TOKEN`
3. The workflow runs daily at 9am UTC. You can also trigger it manually from the Actions tab.

## Monthly routine

At the start of each month, duplicate your template page in Notion and rename it to the new month name (e.g., "May"). The script will pick it up automatically on the next run.

## Adding new merchant rules

Open `src/config.py` and add to `MERCHANT_RULES`. Substring matches are case-insensitive. Order matters - more specific rules should come before less specific ones (e.g., `"uber eats"` before `"uber"`).

After a few weeks of running this, look at what's in your Miscellaneous bucket - those are the merchants that need new rules.

## Troubleshooting

- **"No Notion page titled 'May' found"**: Create the page (or fix its title) and grant your integration access.
- **"Expected 2 child databases on month page, found 1"**: One of the databases on the page isn't a child database. Make sure both Transactions and Categories are inline databases on the page.
- **Plaid auth errors**: Access tokens occasionally need re-auth (e.g., if you change your AMEX password). Re-run `link_account.py` to get a fresh one.
