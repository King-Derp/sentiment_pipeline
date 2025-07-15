"""Defines the DataSink protocol for storage backends."""

from typing import List, Set, Protocol

from reddit_scraper.models.submission import SubmissionRecord


class DataSink(Protocol):
    """
    A protocol that defines the interface for all data storage sinks.

    This ensures that any storage implementation (e.g., CSV, Parquet, database)
    can be used interchangeably by the application's data collection components.
    """

    def append(self, records: List[SubmissionRecord]) -> int:
        """
        Append records to the storage backend.

        Args:
            records: List of submission records to append.

        Returns:
            The number of records successfully appended.
        """
        ...

    def load_ids(self) -> Set[str]:
        """
        Load all existing submission IDs from the storage backend.

        This is used to prevent duplicate data from being fetched and stored.

        Returns:
            A set of unique submission IDs present in the storage.
        """
        ...
