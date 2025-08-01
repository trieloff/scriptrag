"""Base migration class."""

import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime


class Migration(ABC):
    """Base class for database migrations."""

    def __init__(self) -> None:
        """Initialize migration."""
        self.version: int = 0
        self.description: str = ""
        self.applied_at: datetime | None = None

    @abstractmethod
    def up(self, connection: sqlite3.Connection) -> None:
        """Apply the migration.

        Args:
            connection: Database connection
        """
        pass

    @abstractmethod
    def down(self, connection: sqlite3.Connection) -> None:
        """Rollback the migration.

        Args:
            connection: Database connection
        """
        pass

    def __str__(self) -> str:
        """String representation of migration."""
        return f"Migration {self.version}: {self.description}"
