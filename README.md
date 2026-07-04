# Short-Sell Surveillance

A Python program that replays a day's order events and alerts whenever a sell
order carries the wrong `sell_flag` (`Long` / `Short`).

---

## How to run

```bash
# Ensure ref_data.csv and orders.csv sit next to main.py, then:
python main.py
```

No external dependencies are required — the program uses only the Python
standard library.

## Running tests

```bash
python -m pytest tests/ -v
```

> **Note:** `pytest` is the only non-stdlib dependency and is needed solely for
> running the test suite.

---

## Architecture

```
surveillance/
  models.py       Data classes: Order, SymbolState, Alert
  loader.py       CSV readers (ref_data + orders)
  flag_rules.py   Pure decision function — "what flag should this sell have?"
  engine.py       Stateful event replay — processes rows, updates state, emits alerts
  alerts.py       Format an Alert into a printable line
tests/
  test_flag_rules.py   Unit tests for the flag decision logic
  test_engine.py       Unit tests for state mutations and alert generation
main.py           Entry point
```

**Key design choice:** decision logic (`flag_rules`) is completely separated
from state management (`engine`).  `flag_rules.determine_expected_flag` is a
pure function with no side effects — it takes five numbers and returns a string.
The engine is responsible for knowing *when* to call it and *how* to update
state.

---

## Assumptions

1. **Events are processed in file order.**  
   The CSV is assumed to be sorted chronologically.  No secondary sorting is
   applied.

2. **`sell_flag` whitespace is normalised.**  
   The data contains `'Long '` (trailing space) which is stripped to `'Long'`.

3. **Flag is checked on `New` and `Amend` events only.**  
   `NewAccept` and `AmendConfirm` are exchange acknowledgements — they update
   `leaves_qty` but do not trigger flag validation.

4. **On `New`, the order is added to working orders immediately** (with
   `leaves_qty = qty`).  
   This ensures that two rapid-fire sells for the same symbol correctly see each
   other's commitment.  `NewAccept` will update `leaves_qty` if the exchange
   assigns a different value.

5. **On `Amend`, the old order is removed *before* checking the new flag.**  
   This avoids double-counting the commitment.  The new order's `leaves_qty` is
   set to `qty` and corrected by the subsequent `AmendConfirm`.

6. **`Cancel` is a request — no state change.**  
   State only changes on `Cancelled` (exchange confirmation), which removes the
   order.

7. **Missing reference data → position 0, borrow 0.**  
   A symbol that appears in orders but not in `ref_data.csv` is treated as
   having zero initial position and zero borrow allowance.  This means any
   short sell for that symbol would be flagged `Uncovered` — a safe default.

8. **`available_owned = 0` is treated as Short territory.**  
   When we have exactly zero uncommitted shares, any sell must borrow — it's a
   Short (or Uncovered if beyond borrow).

9. **Two independent borrow checks** (as stated in the spec):
   - Combined working-short qty must not exceed `borrow`.
   - Position after *all* sells must not drop below `-borrow`.
   If either is violated, the order is `Uncovered`.

10. **`Filled` events for untracked orders** (e.g. ManualTrade workflows
    submitted outside our `New` event stream) are handled as instant fills —
    position is updated by the event's `qty`.

---

## What I'd add with more time

- **Structured logging** (JSON lines) instead of plain `print()`, so alerts
  can be ingested by a downstream system.
- **More edge-case tests:** amend chains (A → B → C), partial fills followed
  by amends, and symbols with negative `init_position`.
- **Performance:** for 130 k rows the current approach (plain dicts, O(n) scans
  for working qty) is fine, but at much larger scale I'd maintain running totals
  for `working_long_sell_qty` and `working_short_sell_qty` instead of
  recomputing from the orders dict.
- **Input validation:** stricter parsing of timestamps, detection of duplicate
  `client_order_id` values, and graceful handling of malformed rows.
