"""Checkpoint behavior is implemented by the SQLite judgments table.

This compatibility module keeps the responsibility discoverable without duplicating state logic.
"""

from .database import FrontierDatabase

__all__ = ["FrontierDatabase"]

