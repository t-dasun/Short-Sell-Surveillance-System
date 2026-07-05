#!/usr/bin/env python3
"""Short-Sell Surveillance — entry point.

Reads ref_data.csv and orders.csv from the script's directory,
replays every event, and logs mis-flagged sell orders to both
the console and a log file.
"""

import argparse
import logging
import sys
from pathlib import Path

from surveillance.engine import SurveillanceEngine
from surveillance.loader import load_orders, load_ref_data

logger = logging.getLogger("surveillance")


def setup_logging(log_file: Path) -> None:
    """Configure logging to output to both console and file."""
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger("surveillance")
    root_logger.setLevel(logging.DEBUG) # logging.DEBUG ,logging.INFO
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Short-Sell Surveillance Engine")
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("surveillance_alerts.log"),
        help="Path to save output logs (default: surveillance_alerts.log)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Enable terminal dashboard (Box 1: header + alerts).",
    )
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    log_path = args.log_file if args.log_file.is_absolute() else base / args.log_file

    setup_logging(log_path)

    if args.demo:
        # Suppress console logging in demo mode so the UI renders cleanly.
        # Logs still go to the file handler.
        root_logger = logging.getLogger("surveillance")
        root_logger.handlers = [
            h for h in root_logger.handlers
            if not isinstance(h, logging.StreamHandler)
            or isinstance(h, logging.FileHandler)
        ]

    logger.info("Starting Short-Sell Surveillance Engine...")
    logger.info("Logging output to file: %s", log_path)

    ref_path = base / "ref_data.csv"
    orders_path = base / "orders.csv"

    ref_data = load_ref_data(str(ref_path))
    orders = load_orders(str(orders_path))

    engine = SurveillanceEngine(ref_data)

    if args.demo:
        # ── Live terminal dashboard mode ─────────────────────────
        from surveillance.terminal_ui import TerminalUI

        ui = TerminalUI()
        ui.open_header(symbol_count=len(ref_data), total_events=len(orders))

        # Event details go to a separate log file.
        details_path = base / "event_details.log"
        alert_count = 0

        with open(details_path, "w", encoding="utf-8") as details:
            details.write(f"{'#':>7}  {'Timestamp':<10}  {'Event':<14}  "
                          f"{'Symbol':<8}  {'Side':<5}  {'OrderID':<12}  "
                          f"{'Qty':>8}  {'Net Pos':>12}  {'Wk Long':>8}  "
                          f"{'Wk Short':>9}  {'Borrow':>12}\n")
            details.write("─" * 120 + "\n")

            for i, row in enumerate(orders, 1):
                alert = engine.process_event(row)

                # Write event details to the log file.
                symbol = row.get("symbol", "")
                state = engine.states.get(symbol)
                net_pos = state.net_position if state else 0
                wk_long = state.working_long_sell_qty if state else 0
                wk_short = state.working_short_sell_qty if state else 0
                borrow = state.borrow if state else 0

                details.write(
                    f"{i:>7}  {row.get('timestamp', ''):<10}  "
                    f"{row.get('event', ''):<14}  {symbol:<8}  "
                    f"{row.get('side', ''):<5}  "
                    f"{row.get('client_order_id', ''):<12}  "
                    f"{row.get('qty', ''):>8}  {net_pos:>12,}  "
                    f"{wk_long:>8,}  {wk_short:>9,}  {borrow:>12,}\n"
                )

                if alert is not None:
                    alert_count += 1
                    ui.add_alert(alert)

        ui.close_box(alert_count, len(orders))
        print(f"  Event details saved to: {details_path}")
        print()
    else:
        # ── Standard logging mode (no terminal UI) ───────────────
        alert_count = 0
        for row in orders:
            alert = engine.process_event(row)
            if alert is not None:
                alert_count += 1

        logger.info(
            "Surveillance complete. %d alert(s) raised across %d events.",
            alert_count, len(orders),
        )


if __name__ == "__main__":
    main()
