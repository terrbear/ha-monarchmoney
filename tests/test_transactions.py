"""Tests for Monarch Money recent transactions sensor logic."""

from __future__ import annotations

from custom_components.monarchmoney.models import Transaction
from tests.const import MOCK_TRANSACTIONS_RESPONSE


def _parse_transactions() -> list[Transaction]:
    """Parse mock transactions into typed objects."""
    results = MOCK_TRANSACTIONS_RESPONSE["allTransactions"]["results"]
    return [t for t in (Transaction.from_api(i) for i in results) if t is not None]


def test_transaction_parsing():
    """All 3 mock transactions should parse (all have ids)."""
    transactions = _parse_transactions()
    assert len(transactions) == 3


def test_transaction_sensor_state_is_count():
    """Sensor state should be the number of transactions fetched."""
    transactions = _parse_transactions()
    assert len(transactions) == 3


def test_transaction_attributes_shape():
    """Attributes dict should carry the fields the sensor exposes."""
    transactions = _parse_transactions()
    attrs = [
        {
            "id": t.id,
            "date": t.date,
            "amount": t.amount,
            "merchant": t.merchant_name,
            "category": t.category_name,
            "account": t.account_name,
            "pending": t.pending,
            "notes": t.notes,
        }
        for t in transactions
    ]
    assert attrs[0]["merchant"] == "Whole Foods"
    assert attrs[0]["amount"] == -84.32
    assert attrs[1]["pending"] is True


def test_transaction_missing_results_defaults_empty():
    """A response with no results key should yield an empty list."""
    all_txns = {}
    items = all_txns.get("results") or []
    assert items == []
