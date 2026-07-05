# Short-Sell Surveillance System

A professional, modular Python surveillance engine that replays a day's order events and raises real-time alerts whenever a sell order carries an incorrect `sell_flag` (`Long` / `Short` / `0-crossing` / `Uncovered`).

---

## How to Run & Environment Setup

### 1. Environment Requirements
- **Python Version:** `>= 3.8` (Tested on Python 3.10 and 3.12).
- **Core Engine:** Uses **100% Python Standard Library** (`csv`, `dataclasses`, `logging`, `pathlib`, `argparse`, `typing`). **No external packages or third-party libraries are required to run `main.py`!**
- **Automated Tests:** See [requirements.txt](file:///home/dasun/Documents/projects/9miles-takehome-assigment/Short-Sell-Surveillance-System/requirements.txt) for the test dependency (`pytest`).

### 2. Running the Surveillance Engine
Ensure `ref_data.csv` and `orders.csv` sit in the project root next to `main.py`, then run:

```bash
# Standard mode (logs alerts and progress to console and file)
python3 main.py

# Live Demo mode (clean terminal box for alerts; event details saved to log file)
python3 main.py --demo
```

By default (`python3 main.py`), the engine prints formatted alerts and execution logs to both your terminal console and a real-time log file (`surveillance_alerts.log`).

**Optional CLI Arguments:**
- `--demo`: Enable live terminal dashboard mode. Displays a clean, formatted terminal box (Box 1) with system statistics and real-time alerts, while saving all 132,117 event processing details and state snapshots to a separate log file (`event_details.log`).
- `--log-file <path>`: Specify a custom path to save output logs (default: `surveillance_alerts.log`).

### 3. Running Automated Tests
To run the complete suite of 27 automated unit tests across order lifecycle events and short-sell flag rules:

```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
```

---

## Architecture & Clean Logging

```
surveillance/
  models.py       Data classes: Order, SymbolState, Alert
  loader.py       CSV readers (ref_data + orders)
  flag_rules.py   Pure decision function — "what flag should this sell have?"
  engine.py       Stateful event replay — processes rows, updates state, emits alerts
  alerts.py       Format an Alert into a printable line and log warnings
  terminal_ui.py  Formatted ASCII dashboard for demo mode (Box 1 display)
tests/
  test_flag_rules.py   Unit tests for the stateless flag decision logic
  test_engine.py       Unit tests for state mutations, execution types, and alert generation
main.py           Entry point & root logging configuration
requirements.txt  Project dependencies and Python version requirements
```

### Logging Architecture
The project implements Python's built-in `logging` module with a **hierarchical tree structure and log propagation**:
- **Root Configuration (`main.py`):** Configures dual output handlers (`StreamHandler` for stdout and `FileHandler` for `surveillance_alerts.log`).
- **Module Loggers (`surveillance.engine` & `surveillance.alerts`):** Child modules instantiate their own named loggers without passing logger objects around. Log events automatically propagate up to the root handlers.
- **Log Levels:**
  - `INFO`: Used for system startup, symbol loading progress, and final summary statistics.
  - `WARNING`: Used for emitting mis-flagged short-sell alerts.
  - `DEBUG`: Available for granular diagnostics and detecting out-of-order network packets.

---

## Key Financial Engineering & Architecture Assumptions

1. **Events are processed in file order.**  
   The CSV is assumed to be sorted chronologically.

2. **`sell_flag` whitespace is normalised.**  
   The data contains `'Long '` (trailing space) which is cleanly stripped to `'Long'`.

3. **Flag is checked on `New` and `Amend` events only.**  
   `NewAccept` and `AmendConfirm` are exchange acknowledgements — they update `leaves_qty` but do not trigger flag validation.

4. **On `New`, the order is added to working orders immediately** (with `leaves_qty = qty`).  
   This ensures that two rapid-fire sells for the same symbol correctly see each other's working commitment.

5. **On `Amend`, the old order is removed *before* checking the new flag.**  
   This avoids double-counting working sell commitments.

6. **`Cancel` and `Cancelled` both remove the referenced order.**  
   In exchange feeds where cancellation requests and acknowledgements might be grouped or simplified, treating both `Cancel` and `Cancelled` as withdrawing the order ensures working sell commitments are immediately released without leaking inventory.

7. **Missing reference data symbols are skipped.**  
   Symbols appearing in `orders.csv` that are not present in `ref_data.csv` are safely ignored by the surveillance engine instead of creating default zero-allowance states.

8. **`Fill` (Partial/Incremental) vs. `Filled` (Complete/Terminal) Executions:**  
   - **`Fill`:** Represents an incremental execution against an active order resting in the market. It updates `net_position` and adjusts `order.leaves_qty`. The order remains open in `open_orders` (so future fills can be tracked) unless `leaves_qty` drops to 0.
   - **`Filled`:** Represents a terminal, 100% complete execution. It immediately removes (`pop`) the order from `open_orders` and updates `net_position` by whatever shares remained. Removing the order automatically drops its working sell commitment to zero.

9. **Why `leaves_qty` is Authoritative over `qty` (`qty != fill_amount`):**  
   In real-world UDP market data feeds (and specifically in this assignment's dataset), network packets can arrive out of chronological order or use cumulative reporting. Calculating traded amounts from authoritative book balance (`fill_amount = order.leaves_qty - new_leaves`) rather than trusting `row["qty"]` makes the engine immune to out-of-order packet delays and prevents double-counting inventory.

10. **Two independent borrow checks** (as stated in the spec):
    - Combined working-short qty must not exceed `borrow`.
    - Position after *all* sells must not drop below `-borrow`.
    If either is violated, the order is flagged `Uncovered`.

---

## What I'd Add with More Performance

- **Performance optimization:** For 130k rows, the current O(n) scans across active orders for working sell quantities take only ~0.3 seconds. At multi-million row scale, I would maintain O(1) running totals for `working_long_sell_qty` and `working_short_sell_qty`. However, in real-world market data feeds where UDP packets can arrive out of order or with timestamp discrepancies, O(1) running counters can drift over time. Maintaining O(n) property-based calculations across active orders ensures state resilience and correctness without risk of drift.
- **Input validation & schema checks:** Stricter parsing of timestamps, detection of duplicate `client_order_id` values across different symbols, and graceful error handling for malformed CSV rows.
