"""Configuration provider protocol.

STAGE 0.5 BOUNDARY — interface only.
Do not add concrete loaders, dotenv readers, or secret managers here.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ConfigurationProvider(Protocol):
    """Provides configuration values to a clank runtime.

    Concrete implementations are deferred beyond Stage 0.5.
    """

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a configuration value by key."""
        ...

    def require(self, key: str) -> Any:
        """Retrieve a required configuration value or raise."""
        ...
