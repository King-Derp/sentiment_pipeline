"""Defines the base protocol for data sinks."""

from typing import Protocol, List, Dict, Set, Any


class BaseSink(Protocol):
    """A protocol that defines the interface for data sinks."""

    def append(self, records: List[Dict[str, Any]]) -> int:
        """Appends a list of records to the sink."""
        ...

    def load_ids(self) -> Set[str]:
        """Loads the set of existing submission IDs from the sink."""
        ...
