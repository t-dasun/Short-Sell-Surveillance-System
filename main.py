#!/usr/bin/env python3
"""Short-Sell Surveillance — entry point.

Reads ref_data.csv and orders.csv from the script's directory,
replays every event, and prints an alert for each mis-flagged sell.
"""

from pathlib import Path

from surveillance.alerts import format_alert
from surveillance.engine import SurveillanceEngine
from surveillance.loader import load_orders, load_ref_data


def main() -> None:
    base = Path(__file__).resolve().parent
    ref_path = base / "ref_data.csv"
    orders_path = base / "orders.csv"

    ref_data = load_ref_data(str(ref_path))
    orders = load_orders(str(orders_path))

    engine = SurveillanceEngine(ref_data)

    alert_count = 0
    for row in orders:
        alert = engine.process_event(row)
        if alert is not None:
            print(format_alert(alert))
            alert_count += 1

    print(f"\n--- {alert_count} alert(s) raised across {len(orders)} events ---")


if __name__ == "__main__":
    main()
