"""Unit tests for surveillance.loader utilities.

Tests timestamp parsing and stable reordering of order events.
"""

from surveillance.loader import _parse_timestamp, _reorder_by_timestamp


def test_parse_timestamp_valid():
    """Verify correct conversion of MM:SS.f strings to total seconds."""
    assert _parse_timestamp("00:00.0") == 0.0
    assert _parse_timestamp("00:01.5") == 1.5
    assert _parse_timestamp("32:20.4") == 1940.4
    assert _parse_timestamp("59:59.9") == 3599.9


def test_parse_timestamp_malformed_fallback():
    """Malformed or missing timestamps should gracefully fall back to 0.0."""
    assert _parse_timestamp("bad_time") == 0.0
    assert _parse_timestamp("") == 0.0
    assert _parse_timestamp("12") == 0.0


def test_reorder_by_timestamp_stable():
    """Verify stable sorting by timestamp: same-time events preserve file order."""
    rows = [
        {"timestamp": "00:05.0", "event": "Fill", "id": "3"},
        {"timestamp": "00:01.0", "event": "New", "id": "1"},
        {"timestamp": "00:01.0", "event": "NewAccept", "id": "2"},
    ]

    sorted_rows = _reorder_by_timestamp(rows)

    # 00:01.0 events should come first, preserving New -> NewAccept order
    assert sorted_rows[0]["id"] == "1"
    assert sorted_rows[0]["event"] == "New"
    assert sorted_rows[1]["id"] == "2"
    assert sorted_rows[1]["event"] == "NewAccept"
    assert sorted_rows[2]["id"] == "3"
    assert sorted_rows[2]["event"] == "Fill"
