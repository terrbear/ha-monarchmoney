"""Recent transactions sensor for Monarch Money."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback

from ..const import DOMAIN
from ..entity import MonarchEntity
from ..update_coordinator import MonarchCoordinator


class MonarchRecentTransactionsSensor(MonarchEntity, SensorEntity):
    """Most recent transactions, fetched up to a configurable count."""

    _attr_icon = "mdi:receipt-text-clock"

    def __init__(self, coordinator: MonarchCoordinator, unique_id: str) -> None:
        """Initialize the recent transactions sensor."""
        super().__init__(coordinator, unique_id)
        self._attr_name = "Recent Transactions"
        self._attr_unique_id = f"{DOMAIN}_{unique_id}_recent_transactions"
        self._count: int | None = None
        self._transactions: list[dict[str, Any]] = []

    @property
    def native_value(self) -> int | None:
        """Return the number of transactions fetched."""
        return self._count

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        if not data:
            return

        self._count = len(data.transactions)
        self._transactions = [
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
            for t in data.transactions
        ]

        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the sensor."""
        return {"transactions": self._transactions}
