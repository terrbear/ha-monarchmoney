"""Tests for the monarchmoney.get_transactions service response shaping."""

from __future__ import annotations

from custom_components.monarchmoney.models import Account, Transaction
from tests.const import MOCK_ACCOUNTS_RESPONSE, MOCK_TRANSACTIONS_RESPONSE


def _build_response(raw: dict) -> dict:
    """Mirror the shaping done in the get_transactions service handler."""
    all_txns = raw.get("allTransactions") or {}
    items = all_txns.get("results") or []
    transactions = [t for i in items if (t := Transaction.from_api(i)) is not None]
    return {
        "total_count": all_txns.get("totalCount", len(transactions)),
        "transactions": [
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
        ],
    }


def test_response_total_count_and_items():
    response = _build_response(MOCK_TRANSACTIONS_RESPONSE)
    assert response["total_count"] == 3
    assert len(response["transactions"]) == 3
    assert response["transactions"][0]["merchant"] == "Whole Foods"


def test_response_empty_when_no_results():
    response = _build_response({"allTransactions": {"totalCount": 0, "results": []}})
    assert response["total_count"] == 0
    assert response["transactions"] == []


def test_account_name_resolves_to_id():
    accounts = [Account.from_api(a) for a in MOCK_ACCOUNTS_RESPONSE["accounts"]]
    match = next((a for a in accounts if a.display_name == "Primary Checking"), None)
    assert match is not None
    assert match.id == "acct_checking_1"


def test_unknown_account_name_has_no_match():
    accounts = [Account.from_api(a) for a in MOCK_ACCOUNTS_RESPONSE["accounts"]]
    match = next((a for a in accounts if a.display_name == "Nonexistent"), None)
    assert match is None
