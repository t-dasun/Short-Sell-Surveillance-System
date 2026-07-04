"""CSV loaders for reference data and order events.

Two public functions:
    load_ref_data  → dict[symbol, (init_position, borrow)]
    load_orders    → list of raw row dicts (one per event)
"""

import csv
from typing import Dict, List, Tuple


def load_ref_data(filepath: str) -> Dict[str, Tuple[int, int]]:
    """Read ref_data.csv.

    Returns a dict mapping symbol → (init_position, borrow).
    """
    ref: Dict[str, Tuple[int, int]] = {}
    with open(filepath, newline="") as fh:
        for row in csv.DictReader(fh):
            symbol = row["symbol"].strip()
            init_position = int(row["init_position"].strip())
            borrow = int(row["borrow"].strip())
            ref[symbol] = (init_position, borrow)
    return ref


def load_orders(filepath: str) -> List[Dict[str, str]]:
    """Read orders.csv, returning rows in file order.

    Normalises ``sell_flag`` by stripping whitespace so that
    'Long ' becomes 'Long'.
    """
    rows: List[Dict[str, str]] = []
    with open(filepath, newline="") as fh:
        for row in csv.DictReader(fh):
            row["sell_flag"] = row.get("sell_flag", "").strip()
            rows.append(row)
    return rows
