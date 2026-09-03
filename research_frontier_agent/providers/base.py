from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PaperProvider(ABC):
    """Unified discovery-provider contract."""

    name: str

    @abstractmethod
    def discover(self, from_date: str, to_date: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Return (papers, recoverable_errors)."""
