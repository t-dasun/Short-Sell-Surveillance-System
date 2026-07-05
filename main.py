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
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    log_path = args.log_file if args.log_file.is_absolute() else base / args.log_file

    setup_logging(log_path)
    logger.info("Starting Short-Sell Surveillance Engine...")
    logger.info("Logging output to file: %s", log_path)

    ref_path = base / "ref_data.csv"
    orders_path = base / "orders.csv"

    ref_data = load_ref_data(str(ref_path))
    orders = load_orders(str(orders_path))

    engine = SurveillanceEngine(ref_data)

    alert_count = 0
    for row in orders:
        alert = engine.process_event(row)
        if alert is not None:
            alert_count += 1

    logger.info("Surveillance complete. %d alert(s) raised across %d events.", alert_count, len(orders))


if __name__ == "__main__":
    main()
