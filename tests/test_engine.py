"""Unit tests for the SurveillanceEngine.

Tests verify that state mutations (fills, cancels, amends)
are applied correctly and that alerts fire at the right time.
"""

from surveillance.engine import SurveillanceEngine


# ── helpers ───────────────────────────────────────────────────────


def _engine(init_pos: int = 0, borrow: int = 10_000) -> SurveillanceEngine:
    """Create an engine with a single symbol 'TEST'."""
    return SurveillanceEngine({"TEST": (init_pos, borrow)})


def _row(**overrides) -> dict:
    """Build a minimal event row, overriding any fields."""
    base = {
        "timestamp": "00:00.0",
        "event": "New",
        "symbol": "TEST",
        "client_order_id": "1",
        "orig_client_order_id": "",
        "side": "Buy",
        "qty": "100",
        "price": "10.0",
        "leaves_qty": "",
        "source": "AutoTrade",
        "sell_flag": "Long",
    }
    base.update(overrides)
    return base


# ── fill tests ────────────────────────────────────────────────────


def test_fill_reduces_correct_order():
    """A partial fill should reduce leaves_qty and update position."""
    engine = _engine(init_pos=1000)

    # Submit a buy order.
    engine.process_event(_row(event="New", client_order_id="B1", side="Buy", qty="500"))
    engine.process_event(
        _row(event="NewAccept", client_order_id="B1", side="Buy", qty="500", leaves_qty="500")
    )

    # Partial fill of 200 shares.
    engine.process_event(
        _row(event="Fill", client_order_id="B1", side="Buy", qty="200", leaves_qty="300")
    )

    state = engine.states["TEST"]
    assert state.open_orders["B1"].leaves_qty == 300
    assert state.net_position == 1200  # 1000 + 200 filled


def test_fill_removes_order_when_fully_filled():
    """A fill that brings leaves to 0 should remove the order."""
    engine = _engine(init_pos=1000)

    engine.process_event(_row(event="New", client_order_id="B1", side="Buy", qty="500"))
    engine.process_event(
        _row(event="NewAccept", client_order_id="B1", side="Buy", qty="500", leaves_qty="500")
    )
    engine.process_event(
        _row(event="Fill", client_order_id="B1", side="Buy", qty="500", leaves_qty="0")
    )

    state = engine.states["TEST"]
    assert "B1" not in state.open_orders
    assert state.net_position == 1500  # 1000 + 500


# ── cancel tests ──────────────────────────────────────────────────


def test_cancel_removes_correct_order():
    """Cancel and Cancelled should both remove the referenced order."""
    engine = _engine(init_pos=1000)

    engine.process_event(
        _row(event="New", client_order_id="S1", side="Sell", qty="100", sell_flag="Long")
    )
    assert "S1" in engine.states["TEST"].open_orders

    # Cancel removes the order under the assignment's simplified rules.
    engine.process_event(
        _row(event="Cancel", client_order_id="C1", orig_client_order_id="S1")
    )
    assert "S1" not in engine.states["TEST"].open_orders

    engine.process_event(
        _row(event="New", client_order_id="S1", side="Sell", qty="100", sell_flag="Long")
    )

    # Cancelled uses the same removal logic.
    engine.process_event(
        _row(
            event="Cancelled",
            client_order_id="C1",
            orig_client_order_id="S1",
            qty="100",
            leaves_qty="0",
        )
    )
    assert "S1" not in engine.states["TEST"].open_orders


# ── amend tests ───────────────────────────────────────────────────


def test_amend_replaces_old_order():
    """Amend should remove the old order and add the new one."""
    engine = _engine(init_pos=1000)

    engine.process_event(
        _row(event="New", client_order_id="S1", side="Sell", qty="100", sell_flag="Long")
    )
    assert "S1" in engine.states["TEST"].open_orders

    # Amend S1 → S2 with increased qty.
    engine.process_event(
        _row(
            event="Amend",
            client_order_id="S2",
            orig_client_order_id="S1",
            side="Sell",
            qty="200",
            sell_flag="Long",
        )
    )

    state = engine.states["TEST"]
    assert "S1" not in state.open_orders
    assert "S2" in state.open_orders
    assert state.open_orders["S2"].qty == 200


def test_amend_rechecks_flag():
    """An amend that changes the flag should be re-validated."""
    engine = _engine(init_pos=0, borrow=5000)

    # Submit a sell flagged Long — should alert (no shares to sell Long).
    alert1 = engine.process_event(
        _row(event="New", client_order_id="S1", side="Sell", qty="100", sell_flag="Long")
    )
    assert alert1 is not None
    assert alert1.expected_flag == "Short"

    # Amend to Short — now correct, no alert.
    alert2 = engine.process_event(
        _row(
            event="Amend",
            client_order_id="S2",
            orig_client_order_id="S1",
            side="Sell",
            qty="100",
            sell_flag="Short",
        )
    )
    assert alert2 is None


# ── alert tests ───────────────────────────────────────────────────


def test_new_sell_correct_long_no_alert():
    """A correctly flagged Long sell should produce no alert."""
    engine = _engine(init_pos=500)
    alert = engine.process_event(
        _row(event="New", client_order_id="S1", side="Sell", qty="100", sell_flag="Long")
    )
    assert alert is None


def test_new_sell_long_should_be_short_alert():
    """Sell flagged Long but position is 0 → expected Short → alert."""
    engine = _engine(init_pos=0, borrow=5000)
    alert = engine.process_event(
        _row(event="New", client_order_id="S1", side="Sell", qty="100", sell_flag="Long")
    )
    assert alert is not None
    assert alert.actual_flag == "Long"
    assert alert.expected_flag == "Short"


def test_new_sell_short_should_be_long_alert():
    """Sell flagged Short but we own enough → expected Long → alert."""
    engine = _engine(init_pos=800)
    alert = engine.process_event(
        _row(event="New", client_order_id="S1", side="Sell", qty="100", sell_flag="Short")
    )
    assert alert is not None
    assert alert.actual_flag == "Short"
    assert alert.expected_flag == "Long"


def test_buy_order_no_alert():
    """Buy orders should never trigger alerts."""
    engine = _engine(init_pos=0)
    alert = engine.process_event(
        _row(event="New", client_order_id="B1", side="Buy", qty="100")
    )
    assert alert is None


def test_missing_ref_data_symbol_is_skipped():
    """Symbol not in ref_data should not be checked or tracked."""
    engine = _engine()  # only 'TEST' in ref_data
    alert = engine.process_event(
        _row(
            event="New",
            symbol="UNKNOWN",
            client_order_id="S1",
            side="Sell",
            qty="100",
            sell_flag="Short",
        )
    )
    assert alert is None
    assert "UNKNOWN" not in engine.states


def test_sell_flag_whitespace_normalised():
    """sell_flag='Long ' (trailing space) should be treated as 'Long'."""
    engine = _engine(init_pos=500)
    alert = engine.process_event(
        _row(
            event="New",
            client_order_id="S1",
            side="Sell",
            qty="100",
            sell_flag="Long ",  # trailing space
        )
    )
    # The engine normalises whitespace, so 'Long ' becomes 'Long'.
    # With 500 position and qty 100, Long is correct → no alert.
    assert alert is None


def test_working_qty_affects_subsequent_orders():
    """Two consecutive Long sells — the second should see reduced available."""
    engine = _engine(init_pos=150, borrow=5000)

    # First sell: 100 shares Long.  available = 150 ≥ 100 → Long, OK.
    alert1 = engine.process_event(
        _row(event="New", client_order_id="S1", side="Sell", qty="100", sell_flag="Long")
    )
    assert alert1 is None

    # Second sell: 100 shares Long.  available = 150 - 100 = 50 < 100 → 0-crossing!
    alert2 = engine.process_event(
        _row(event="New", client_order_id="S2", side="Sell", qty="100", sell_flag="Long")
    )
    assert alert2 is not None
    assert alert2.expected_flag == "0-crossing"
