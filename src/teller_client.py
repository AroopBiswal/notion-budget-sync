"""Teller.io client: fetch recent transactions."""
from datetime import date, timedelta
from typing import List, Dict

import requests

from .config import TELLER_ACCESS_TOKEN, TELLER_CERT, TELLER_KEY, TELLER_ACCOUNT_ID

_BASE_URL = "https://api.teller.io"


def fetch_transactions(lookback_days: int) -> List[Dict]:
    """Fetch transactions from the linked account for the last N days.

    Returns a list of dicts with keys: id, date, name, amount.
    Teller returns negative amounts for debits; we flip to positive.
    """
    cutoff = date.today() - timedelta(days=lookback_days)
    cert = (TELLER_CERT, TELLER_KEY) if TELLER_CERT and TELLER_KEY else None

    all_txns = []
    params: Dict = {"count": 100}

    while True:
        resp = requests.get(
            f"{_BASE_URL}/accounts/{TELLER_ACCOUNT_ID}/transactions",
            auth=(TELLER_ACCESS_TOKEN, ""),
            cert=cert,
            params=params,
        )
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break

        for t in page:
            txn_date = date.fromisoformat(t["date"])
            if txn_date < cutoff:
                return _normalize(all_txns)
            all_txns.append(t)

        if len(page) < params["count"]:
            break
        # Cursor: pass last transaction's ID to get older ones
        params["from_id"] = page[-1]["id"]

    return _normalize(all_txns)


def _normalize(txns: List[Dict]) -> List[Dict]:
    cleaned = []
    for t in txns:
        if t.get("status") == "pending":
            continue
        amount = -float(t["amount"])  # Teller: negative = debit; flip to positive
        if amount <= 0:
            continue  # credits / refunds
        cleaned.append({
            "id": t["id"],
            "date": t["date"],
            "name": t.get("description") or "Unknown",
            "amount": amount,
        })
    return cleaned
