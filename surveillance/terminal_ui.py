"""Terminal UI — rich formatted dashboard for the surveillance engine.

Provides a visually formatted terminal output with box-drawing characters
and ANSI colors. Used in demo mode (``--demo``) to display the header
and alerts in a single continuous box.

Event processing details are written to a separate log file by main.py.

This module uses only the Python standard library (no external packages).
"""

from .models import Alert


# ── ANSI color codes ─────────────────────────────────────────────


class Colors:
    """ANSI escape codes for terminal colors."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"


# ── Box drawing helpers ──────────────────────────────────────────

BOX_WIDTH = 74


def _top(color: str = Colors.CYAN) -> str:
    return f"{color}┌{'─' * (BOX_WIDTH - 2)}┐{Colors.RESET}"


def _bot(color: str = Colors.CYAN) -> str:
    return f"{color}└{'─' * (BOX_WIDTH - 2)}┘{Colors.RESET}"


def _div(color: str = Colors.CYAN) -> str:
    return f"{color}├{'─' * (BOX_WIDTH - 2)}┤{Colors.RESET}"


def _row(text: str, border: str = Colors.CYAN, fg: str = Colors.WHITE) -> str:
    """Render a single line inside a box, padded to BOX_WIDTH."""
    inner = BOX_WIDTH - 4  # 2 borders + 2 padding spaces
    display = text[:inner].ljust(inner)
    return f"{border}│{Colors.RESET} {fg}{display}{Colors.RESET} {border}│{Colors.RESET}"


# ── Terminal UI class ────────────────────────────────────────────


class TerminalUI:
    """Single-box terminal dashboard: header + scrolling alerts + summary."""

    def __init__(self) -> None:
        self.alert_count = 0

    def open_header(self, symbol_count: int, total_events: int) -> None:
        """Print box top border and header rows. Box stays open for alerts."""
        c = Colors.CYAN
        b = f"{Colors.BOLD}{Colors.CYAN}"
        print()
        print(_top(c))
        print(_row("⚡  SHORT-SELL SURVEILLANCE SYSTEM", c, b))
        print(_div(c))
        print(_row(f"Symbols Loaded:    {symbol_count}", c, Colors.WHITE))
        print(_row(f"Total Events:      {total_events:,}", c, Colors.WHITE))
        print(_row(f"Mode:              Live Demo", c, Colors.GREEN))

    def add_alert(self, alert: Alert) -> None:
        """Append an alert row inside the box."""
        self.alert_count += 1
        c = Colors.CYAN
        print(_div(Colors.RED))
        print(_row(
            f"⚠  ALERT #{self.alert_count}   "
            f"Symbol: {alert.symbol}   Order: {alert.client_order_id}",
            c, f"{Colors.BOLD}{Colors.RED}",
        ))
        print(_row(
            f"   Flagged: {alert.actual_flag}  →  Expected: {alert.expected_flag}",
            c, f"{Colors.BOLD}{Colors.YELLOW}",
        ))
        print(_row(
            f"   Net Pos: {alert.net_position:,}   "
            f"Wk Long: {alert.working_long_sell_qty:,}   "
            f"Wk Short: {alert.working_short_sell_qty:,}   "
            f"Borrow: {alert.borrow:,}",
            c, Colors.WHITE,
        ))

    def close_box(self, alert_count: int, total_events: int) -> None:
        """Close the box with a summary section and bottom border."""
        c = Colors.CYAN
        sc = Colors.GREEN if alert_count == 0 else Colors.YELLOW
        alert_fg = Colors.GREEN if alert_count == 0 else f"{Colors.BOLD}{Colors.RED}"

        print(_div(sc))
        print(_row("✓  SURVEILLANCE COMPLETE", c, f"{Colors.BOLD}{sc}"))
        print(_row(f"   Events Processed:   {total_events:,}", c, Colors.WHITE))
        print(_row(f"   Alerts Raised:      {alert_count}", c, alert_fg))
        print(_bot(c))
        print()
