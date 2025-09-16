"""File and path validators for CLI input."""

from __future__ import annotations

import contextlib
import uuid
from pathlib import Path

from scriptrag.cli.validators.base import ValidationError, Validator


class FileValidator(Validator[Path]):
    """Validator for file paths."""

    def __init__(
        self,
        must_exist: bool = True,
        must_be_file: bool = True,
        extensions: list[str] | None = None,
    ) -> None:
        """Initialize file validator.

        Args:
            must_exist: Whether file must exist
            must_be_file: Whether path must be a file (not directory)
            extensions: Allowed file extensions (e.g., [".fountain", ".txt"])
        """
        self.must_exist = must_exist
        self.must_be_file = must_be_file
        self.extensions = extensions

    def validate(self, value: str | Path) -> Path:
        """Validate file path.

        Args:
            value: File path to validate

        Returns:
            Validated Path object

        Raises:
            ValidationError: If validation fails
        """
        if isinstance(value, str):
            path = Path(value).expanduser().resolve()
        else:
            path = value.expanduser().resolve()

        if self.must_exist and not path.exists():
            raise ValidationError(f"File does not exist: {path}")

        if self.must_be_file and path.exists() and not path.is_file():
            raise ValidationError(f"Path is not a file: {path}")

        if self.extensions and path.suffix.lower() not in self.extensions:
            raise ValidationError(
                f"Invalid file extension: {path.suffix}. "
                f"Expected one of: {', '.join(self.extensions)}"
            )

        return path


class DirectoryValidator(Validator[Path]):
    """Validator for directory paths."""

    def __init__(
        self,
        must_exist: bool = True,
        create_if_missing: bool = False,
        must_be_writable: bool = False,
    ) -> None:
        """Initialize directory validator.

        Args:
            must_exist: Whether directory must exist
            create_if_missing: Create directory if it doesn't exist
            must_be_writable: Check if directory is writable
        """
        self.must_exist = must_exist
        self.create_if_missing = create_if_missing
        self.must_be_writable = must_be_writable

    def validate(self, value: str | Path) -> Path:
        """Validate directory path.

        Args:
            value: Directory path to validate

        Returns:
            Validated Path object

        Raises:
            ValidationError: If validation fails
        """
        if isinstance(value, str):
            path = Path(value).expanduser().resolve()
        else:
            path = value.expanduser().resolve()

        if not path.exists():
            if self.create_if_missing:
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    raise ValidationError(
                        f"Failed to create directory {path}: {e}"
                    ) from e
            elif self.must_exist:
                raise ValidationError(f"Directory does not exist: {path}")

        if path.exists() and not path.is_dir():
            raise ValidationError(f"Path is not a directory: {path}")

        if self.must_be_writable and path.exists():
            # Check if we can write to the directory
            # Use a unique filename to avoid race conditions with concurrent processes
            test_file = path / f".write_test_{uuid.uuid4().hex}"
            try:
                test_file.touch()
                test_file.unlink()
            except Exception as exc:
                # Clean up in case touch succeeded but unlink failed
                with contextlib.suppress(Exception):
                    test_file.unlink(missing_ok=True)
                raise ValidationError(f"Directory is not writable: {path}") from exc

        return path


class ConfigFileValidator(FileValidator):
    """Validator specifically for configuration files."""

    def __init__(self) -> None:
        """Initialize config file validator."""
        super().__init__(
            must_exist=True,
            must_be_file=True,
            extensions=[".yaml", ".yml", ".json", ".toml"],
        )
