"""Read transaction files into a uniform (headers, rows) format."""
from pathlib import Path
from typing import List, Dict, Tuple

import pandas as pd


def read_file(path: str) -> Tuple[List[str], List[Dict]]:
    """Auto-detect format from extension and return (headers, rows)."""
    ext = Path(path).suffix.lower()

    if ext == ".csv":
        df = pd.read_csv(path, dtype=str)
    elif ext == ".tsv":
        df = pd.read_csv(path, sep="\t", dtype=str)
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(path, dtype=str)
    elif ext == ".json":
        df = pd.read_json(path)
        df = df.astype(str)
    else:
        raise ValueError(
            f"Unsupported file format '{ext}'. "
            "Supported: .csv, .tsv, .xlsx, .xls, .json"
        )

    headers = list(df.columns)
    rows = df.to_dict(orient="records")
    return headers, rows
