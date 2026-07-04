"""Unit tests for surveillance.flag_rules.determine_expected_flag.

Each test constructs a specific position / working-order scenario
and asserts the expected flag string.
"""

from surveillance.flag_rules import determine_expected_flag


# ── Long sell tests ───────────────────────────────────────────────


def test_long_when_enough_position():
    """Hold 500 shares, no working sells, sell 200 → Long."""
    result = determine_expected_flag(
        net_position=500,
        working_long_sell_qty=0,
        working_short_sell_qty=0,
        borrow=1000,
        order_qty=200,
    )
    assert result == "Long"


def test_long_exactly_at_position():
    """Hold 200 shares, sell exactly 200 → Long (boundary)."""
    result = determine_expected_flag(
        net_position=200,
        working_long_sell_qty=0,
        working_short_sell_qty=0,
        borrow=1000,
        order_qty=200,
    )
    assert result == "Long"


def test_long_with_working_long_sells_still_enough():
    """Hold 500, already committed 200 to Long sells, sell 200 → Long.

    available_owned = 500 - 200 = 300 ≥ 200 → Long.
    """
    result = determine_expected_flag(
        net_position=500,
        working_long_sell_qty=200,
        working_short_sell_qty=0,
        borrow=1000,
        order_qty=200,
    )
    assert result == "Long"


# ── Short sell tests ──────────────────────────────────────────────


def test_long_when_zero_available_should_be_short():
    """Hold 0 shares, sell 100 → Short (nothing to cover a Long sell)."""
    result = determine_expected_flag(
        net_position=0,
        working_long_sell_qty=0,
        working_short_sell_qty=0,
        borrow=1000,
        order_qty=100,
    )
    assert result == "Short"


def test_short_within_borrow():
    """Already net-short -100, sell 200, borrow=1000 → Short."""
    result = determine_expected_flag(
        net_position=-100,
        working_long_sell_qty=0,
        working_short_sell_qty=0,
        borrow=1000,
        order_qty=200,
    )
    assert result == "Short"


def test_short_exactly_at_borrow():
    """Working-short 900 + new 100 = 1000 = borrow → Short (boundary)."""
    result = determine_expected_flag(
        net_position=0,
        working_long_sell_qty=0,
        working_short_sell_qty=900,
        borrow=1000,
        order_qty=100,
    )
    assert result == "Short"


def test_negative_init_position_short():
    """Start day short -500, sell 100, borrow=1000 → Short."""
    result = determine_expected_flag(
        net_position=-500,
        working_long_sell_qty=0,
        working_short_sell_qty=0,
        borrow=1000,
        order_qty=100,
    )
    assert result == "Short"


# ── Zero-crossing tests ──────────────────────────────────────────


def test_zero_crossing():
    """Hold 100, sell 125 → 0-crossing (cannot be one order)."""
    result = determine_expected_flag(
        net_position=100,
        working_long_sell_qty=0,
        working_short_sell_qty=0,
        borrow=1000,
        order_qty=125,
    )
    assert result == "0-crossing"


def test_zero_crossing_with_working_long():
    """Hold 500, already committed 400 Long, sell 200.

    available_owned = 500 - 400 = 100 → 0 < 100 < 200 → 0-crossing.
    """
    result = determine_expected_flag(
        net_position=500,
        working_long_sell_qty=400,
        working_short_sell_qty=0,
        borrow=1000,
        order_qty=200,
    )
    assert result == "0-crossing"


# ── Uncovered tests ───────────────────────────────────────────────


def test_short_exceeds_borrow_uncovered():
    """Working-short already at 2000 = borrow, another 100 → Uncovered."""
    result = determine_expected_flag(
        net_position=-100,
        working_long_sell_qty=0,
        working_short_sell_qty=2000,
        borrow=2000,
        order_qty=100,
    )
    assert result == "Uncovered"


def test_uncovered_position_after_all_sells():
    """Working-short within borrow, but negative position pushes past limit.

    available_owned = -100, working_short = 700, new = 50, borrow = 800
    Condition 1: 700 + 50 = 750 ≤ 800 → OK
    Condition 2: -100 - 700 - 50 = -850 < -800 → Uncovered
    """
    result = determine_expected_flag(
        net_position=-100,
        working_long_sell_qty=0,
        working_short_sell_qty=700,
        borrow=800,
        order_qty=50,
    )
    assert result == "Uncovered"


def test_zero_borrow_means_every_short_uncovered():
    """borrow=0, any short sell is uncovered."""
    result = determine_expected_flag(
        net_position=0,
        working_long_sell_qty=0,
        working_short_sell_qty=0,
        borrow=0,
        order_qty=1,
    )
    assert result == "Uncovered"
