"""Plaid client: fetch recent AMEX transactions."""
from datetime import date, timedelta
from typing import List, Dict

from plaid.api import plaid_api
from plaid.configuration import Configuration
from plaid.api_client import ApiClient
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions

from .config import PLAID_CLIENT_ID, PLAID_SECRET, PLAID_ENV, PLAID_ACCESS_TOKEN


def _client() -> plaid_api.PlaidApi:
    host_map = {
        "sandbox": "https://sandbox.plaid.com",
        "development": "https://development.plaid.com",
        "production": "https://production.plaid.com",
    }
    config = Configuration(
        host=host_map[PLAID_ENV],
        api_key={"clientId": PLAID_CLIENT_ID, "secret": PLAID_SECRET},
    )
    return plaid_api.PlaidApi(ApiClient(config))


def fetch_transactions(lookback_days: int) -> List[Dict]:
    """Fetch transactions from the linked AMEX account for the last N days.

    Returns a list of dicts with keys: id, date, name, amount.
    Note: Plaid returns positive amounts for debits (charges).
    """
    end = date.today()
    start = end - timedelta(days=lookback_days)

    client = _client()
    all_txns = []
    offset = 0
    page_size = 100

    while True:
        request = TransactionsGetRequest(
            access_token=PLAID_ACCESS_TOKEN,
            start_date=start,
            end_date=end,
            options=TransactionsGetRequestOptions(count=page_size, offset=offset),
        )
        response = client.transactions_get(request)
        txns = response["transactions"]
        all_txns.extend(txns)

        if len(all_txns) >= response["total_transactions"]:
            break
        offset += page_size

    # Normalize. Skip pending and refunds (negative amounts in Plaid).
    cleaned = []
    for t in all_txns:
        if t.get("pending"):
            continue
        amount = float(t["amount"])
        if amount <= 0:
            # refunds / payments to the card - skip
            continue
        cleaned.append({
            "id": t["transaction_id"],
            "date": t["date"].isoformat() if hasattr(t["date"], "isoformat") else str(t["date"]),
            "name": t.get("merchant_name") or t.get("name") or "Unknown",
            "amount": amount,
        })

    return cleaned
