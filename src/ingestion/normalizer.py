"""Apply a schema mapping to raw rows, producing normalized transaction dicts."""
import hashlib
from typing import Dict, List

import pandas as pd


def normalize(rows: List[Dict], mapping: Dict) -> List[Dict]:
    """Return normalized transactions: {id, date, merchant, amount}.

    Charges are always positive after normalization.
    Rows with unparseable dates/amounts or non-positive amounts are dropped.
    """
    date_col = mapping["date_col"]
    merchant_col = mapping["merchant_col"]
    amount_col = mapping["amount_col"]
    txn_id_col = mapping.get("txn_id_col")
    amount_sign = mapping.get("amount_sign", "positive_is_charge")

    result = []
    for row in rows:
        raw_date = row.get(date_col)
        raw_amount = row.get(amount_col)

        if raw_date is None or raw_amount is None:
            continue

        try:
            parsed_date = pd.to_datetime(str(raw_date)).date()
            amount = float(str(raw_amount).replace(",", "").replace("$", ""))
        except (ValueError, TypeError):
            continue

        if amount_sign == "negative_is_charge":
            amount = -amount

        if amount <= 0:
            continue  # refund or payment, skip

        merchant = str(row.get(merchant_col) or "Unknown").strip()
        date_str = parsed_date.isoformat()

        if txn_id_col and row.get(txn_id_col):
            txn_id = str(row[txn_id_col]).strip()
        else:
            raw = f"{date_str}|{merchant}|{amount:.2f}"
            txn_id = hashlib.sha1(raw.encode()).hexdigest()[:16]

        result.append({
            "id": txn_id,
            "date": date_str,
            "merchant": merchant,
            "amount": round(amount, 2),
        })

    return result
