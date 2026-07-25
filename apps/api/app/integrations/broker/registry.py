"""Single lookup point for broker adapters.

The sync worker and broker_connections service call get_adapter(broker_name)
rather than branching on broker name directly — adding a second broker (Dhan,
per docs/roadmap.md Phase 1) means registering it here, not touching callers.
"""

from __future__ import annotations

from app.integrations.broker.base import BrokerAdapter
from app.integrations.broker.upstox import UpstoxAdapter

_ADAPTERS: dict[str, type[BrokerAdapter]] = {
    "upstox": UpstoxAdapter,
}


class UnsupportedBrokerError(Exception):
    """Raised when broker_name doesn't match a registered adapter."""


def get_adapter(broker_name: str) -> BrokerAdapter:
    adapter_cls = _ADAPTERS.get(broker_name)
    if adapter_cls is None:
        raise UnsupportedBrokerError(f"No adapter registered for broker '{broker_name}'.")
    return adapter_cls()


def supported_brokers() -> list[str]:
    return list(_ADAPTERS.keys())
