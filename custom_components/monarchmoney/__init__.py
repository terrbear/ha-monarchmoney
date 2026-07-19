"""The Monarch Money integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import (
    CONF_ENABLE_AGGREGATED_HOLDINGS,
    CONF_ENABLE_CREDIT_SCORE,
    CONF_ENABLE_HOLDINGS,
    CONF_ENABLE_RECURRING,
    DOMAIN,
    PLATFORMS,
)
from .models import Transaction
from .update_coordinator import MonarchCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_GET_TRANSACTIONS = "get_transactions"

GET_TRANSACTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional("start_date"): cv.string,
        vol.Optional("end_date"): cv.string,
        vol.Optional("limit", default=100): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=1000)
        ),
        vol.Optional("offset", default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional("search", default=""): cv.string,
        vol.Optional("account"): cv.string,
    }
)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entries to current version."""
    if config_entry.version == 1:
        _LOGGER.debug("Migrating config entry from version 1 to 2")
        hass.config_entries.async_update_entry(config_entry, version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Monarch Money from a config entry."""
    coordinator = MonarchCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    if not hass.services.has_service(DOMAIN, SERVICE_GET_TRANSACTIONS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_TRANSACTIONS,
            _async_get_transactions_service(hass),
            schema=GET_TRANSACTIONS_SCHEMA,
            supports_response=SupportsResponse.ONLY,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_GET_TRANSACTIONS)
    return ok


def _async_get_transactions_service(hass: HomeAssistant):
    """Build the get_transactions service handler bound to this hass instance."""

    async def _handler(call: ServiceCall) -> ServiceResponse:
        coordinators: list[MonarchCoordinator] = list(hass.data.get(DOMAIN, {}).values())
        if not coordinators:
            raise HomeAssistantError("No Monarch Money account is configured")
        coordinator = coordinators[0]

        start_date = call.data.get("start_date")
        end_date = call.data.get("end_date")
        account_ids: list[str] = []
        account_name = call.data.get("account")
        if account_name:
            data = coordinator.data
            match = next(
                (
                    a
                    for a in (data.accounts if data else [])
                    if a.display_name == account_name
                ),
                None,
            )
            if match is None:
                raise HomeAssistantError(f"Unknown account: {account_name}")
            account_ids = [match.id]

        try:
            raw = await coordinator.api.get_transactions(
                limit=call.data["limit"],
                offset=call.data["offset"],
                start_date=start_date,
                end_date=end_date,
                search=call.data["search"],
                account_ids=account_ids,
            )
        except Exception as err:
            raise HomeAssistantError(f"Failed to fetch transactions: {err}") from err
        all_txns = raw.get("allTransactions") or {}
        items = all_txns.get("results") or []
        transactions = [
            t for i in items if (t := Transaction.from_api(i)) is not None
        ]

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

    return _handler


async def _async_update_options(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Update options and clean up entities for disabled features."""
    _cleanup_disabled_entities(hass, config_entry)
    await hass.config_entries.async_reload(config_entry.entry_id)


def _cleanup_disabled_entities(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> None:
    """Remove entity registry entries for optional features that are now disabled."""
    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_config_entry(ent_reg, config_entry.entry_id)
    options = config_entry.options
    uid = config_entry.unique_id
    prefix = f"{DOMAIN}_{uid}_"

    for entry in entries:
        should_remove = False

        # Calendar entities only come from recurring transactions
        if entry.domain == "calendar" and not options.get(
            CONF_ENABLE_RECURRING, False
        ):
            should_remove = True

        # Credit score sensors (per-user: credit_score_{user_id}, legacy: credit_score)
        elif (
            entry.domain == "sensor"
            and not options.get(CONF_ENABLE_CREDIT_SCORE, False)
            and (
                entry.unique_id == f"{prefix}credit_score"
                or entry.unique_id.startswith(f"{prefix}credit_score_")
            )
        ):
            should_remove = True

        # Aggregated holding sensors: unique_id contains "holding_agg_"
        elif (
            entry.domain == "sensor"
            and not options.get(CONF_ENABLE_AGGREGATED_HOLDINGS, False)
            and entry.unique_id.startswith(f"{prefix}holding_agg_")
        ):
            should_remove = True

        # Per-account holding sensors: unique_id contains "holding_acct_"
        elif (
            entry.domain == "sensor"
            and not options.get(CONF_ENABLE_HOLDINGS, False)
            and entry.unique_id.startswith(f"{prefix}holding_acct_")
        ):
            should_remove = True

        if should_remove:
            _LOGGER.debug(
                "Removing entity %s (feature disabled)", entry.entity_id
            )
            ent_reg.async_remove(entry.entity_id)


