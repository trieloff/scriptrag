"""Base validator classes for CLI input."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, message: str, field: str | None = None) -> None:
        """Initialize validation error.

        Args:
            message: Error message
            field: Optional field name that failed validation
        """
        self.field = field
        super().__init__(message)


class Validator(ABC, Generic[T]):
    """Base class for input validators."""

    @abstractmethod
    def validate(self, value: Any) -> T:
        """Validate input value.

        Args:
            value: Value to validate

        Returns:
            Validated value, possibly transformed

        Raises:
            ValidationError: If validation fails
        """
        pass

    def validate_required(self, value: Any, field_name: str) -> Any:
        """Validate that a value is not None or empty.

        Args:
            value: Value to check
            field_name: Name of field for error message

        Returns:
            The value if valid

        Raises:
            ValidationError: If value is None or empty
        """
        if value is None:
            raise ValidationError(f"{field_name} is required", field_name)
        if isinstance(value, str) and not value.strip():
            raise ValidationError(f"{field_name} cannot be empty", field_name)
        return value

    def validate_type(self, value: Any, expected_type: type, field_name: str) -> Any:
        """Validate that a value is of expected type.

        Args:
            value: Value to check
            expected_type: Expected type
            field_name: Name of field for error message

        Returns:
            The value if valid

        Raises:
            ValidationError: If value is not of expected type
        """
        if not isinstance(value, expected_type):
            raise ValidationError(
                f"{field_name} must be {expected_type.__name__}, "
                f"got {type(value).__name__}",
                field_name,
            )
        return value

    def validate_range(
        self,
        value: int | float,
        min_val: int | float | None = None,
        max_val: int | float | None = None,
        field_name: str = "value",
    ) -> int | float:
        """Validate that a numeric value is within range.

        Args:
            value: Value to check
            min_val: Minimum allowed value (inclusive)
            max_val: Maximum allowed value (inclusive)
            field_name: Name of field for error message

        Returns:
            The value if valid

        Raises:
            ValidationError: If value is outside range
        """
        if min_val is not None and value < min_val:
            raise ValidationError(
                f"{field_name} must be >= {min_val}, got {value}", field_name
            )
        if max_val is not None and value > max_val:
            raise ValidationError(
                f"{field_name} must be <= {max_val}, got {value}", field_name
            )
        return value


class CompositeValidator(Validator[T]):
    """Validator that combines multiple validators."""

    def __init__(self, validators: list[Validator]) -> None:
        """Initialize composite validator.

        Args:
            validators: List of validators to apply in order
        """
        self.validators = validators

    def validate(self, value: Any) -> T:
        """Apply all validators in sequence.

        Args:
            value: Value to validate

        Returns:
            Validated value after all transformations

        Raises:
            ValidationError: If any validator fails
        """
        result = value
        for validator in self.validators:
            result = validator.validate(result)
        return result  # type: ignore[no-any-return]
