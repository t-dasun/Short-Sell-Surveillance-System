"""CSV loaders for reference data and order events.

Two public functions:
    load_ref_data  → dict[symbol, (init_position, borrow)]
    load_orders    → list of raw row dicts (one per event)
"""

import csv
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger("surveillance.loader")


# Reads ref_data.csv, returning a dict mapping symbol → (init_position, borrow).
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


def _parse_timestamp(ts: str) -> float:
    """Convert a ``MM:SS.f`` timestamp string to total seconds.

    Examples:  '32:20.4' → 1940.4,  '00:01.0' → 1.0
    Falls back to 0.0 on malformed input so sorting never crashes.
    """
    try:
        parts = ts.strip().split(":")
        minutes = int(parts[0])
        seconds = float(parts[1])
        return minutes * 60 + seconds
    except (ValueError, IndexError):
        return 0.0


def _reorder_by_timestamp(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Stable-sort rows by parsed timestamp.

    Python's ``sorted()`` is a *stable* sort (Timsort), so rows that
    share the same timestamp keep their original file order — this
    preserves the correct lifecycle sequence for events like
    New → NewAccept → Fill that happen at the same instant.

    Returns a new list; the original is not modified.
    """
    before = len(rows)
    sorted_rows = sorted(rows, key=lambda r: _parse_timestamp(r.get("timestamp", "")))

    # Count how many rows actually moved position.
    moved = sum(1 for a, b in zip(rows, sorted_rows) if a is not b)
    if moved:
        logger.info(
            "Timestamp reorder: %d of %d rows changed position.",
            moved, before,
        )
    else:
        logger.info("Timestamp reorder: all %d rows already in order.", before)

    return sorted_rows


# Reads orders.csv, returning rows in file order as a list of dicts.
def load_orders(
    filepath: str,
    sort_by_timestamp: bool = False,
) -> List[Dict[str, str]]:
    """Read orders.csv, returning rows in file order.

    Normalises ``sell_flag`` by stripping whitespace so that
    'Long ' becomes 'Long'.

    Parameters
    ----------
    filepath:
        Path to the CSV file.
    sort_by_timestamp:
        If ``True``, stable-sort the rows by their timestamp column
        before returning.  Same-timestamp events keep their original
        file order.  Default is ``False`` (file order preserved as-is).
    """
    rows: List[Dict[str, str]] = []
    with open(filepath, newline="") as fh:
        for row in csv.DictReader(fh):
            row["sell_flag"] = row.get("sell_flag", "").strip()
            rows.append(row)

    if sort_by_timestamp:
        rows = _reorder_by_timestamp(rows)

    return rows

