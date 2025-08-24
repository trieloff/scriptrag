"""Command composition utilities for complex CLI operations."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from scriptrag.config import get_logger

logger = get_logger(__name__)


@dataclass
class CommandStep:
    """Represents a single step in a command composition."""

    name: str
    function: Callable
    args: tuple = ()
    kwargs: dict[str, Any] | None = None
    on_error: str = "abort"  # "abort", "continue", "retry"
    retry_count: int = 0

    def __post_init__(self) -> None:
        """Initialize kwargs if None."""
        if self.kwargs is None:
            self.kwargs = {}


@dataclass
class CommandResult:
    """Result of a command execution."""

    success: bool
    data: Any = None
    error: Exception | None = None
    step_name: str | None = None


class CommandComposer:
    """Composes and executes multiple command steps."""

    def __init__(self) -> None:
        """Initialize command composer."""
        self.steps: list[CommandStep] = []
        self.results: list[CommandResult] = []

    def add_step(
        self,
        name: str,
        function: Callable,
        *args,
        on_error: str = "abort",
        retry_count: int = 0,
        **kwargs,
    ) -> "CommandComposer":
        """Add a step to the composition.

        Args:
            name: Step name for identification
            function: Function to execute
            *args: Positional arguments for function
            on_error: Error handling strategy
            retry_count: Number of retries on failure
            **kwargs: Keyword arguments for function

        Returns:
            Self for chaining
        """
        step = CommandStep(
            name=name,
            function=function,
            args=args,
            kwargs=kwargs,
            on_error=on_error,
            retry_count=retry_count,
        )
        self.steps.append(step)
        return self

    def execute(self) -> list[CommandResult]:
        """Execute all steps in sequence.

        Returns:
            List of results from each step
        """
        self.results = []

        for step in self.steps:
            result = self._execute_step(step)
            self.results.append(result)

            # Handle errors based on strategy
            if not result.success:
                if step.on_error == "abort":
                    logger.error(f"Step {step.name} failed, aborting")
                    break
                if step.on_error == "continue":
                    logger.warning(f"Step {step.name} failed, continuing")
                    continue

        return self.results

    def _execute_step(self, step: CommandStep) -> CommandResult:
        """Execute a single step with retry logic.

        Args:
            step: Step to execute

        Returns:
            Command result
        """
        attempts = 0
        max_attempts = step.retry_count + 1

        while attempts < max_attempts:
            try:
                logger.debug(f"Executing step: {step.name} (attempt {attempts + 1})")
                result = step.function(*step.args, **step.kwargs)
                return CommandResult(
                    success=True,
                    data=result,
                    step_name=step.name,
                )
            except Exception as e:
                attempts += 1
                if attempts >= max_attempts:
                    logger.error(
                        f"Step {step.name} failed after {attempts} attempts: {e}"
                    )
                    return CommandResult(
                        success=False,
                        error=e,
                        step_name=step.name,
                    )
                logger.warning(
                    f"Step {step.name} failed, retrying... ({attempts}/{max_attempts})"
                )

        # Should not reach here
        return CommandResult(
            success=False,
            error=Exception("Unexpected error in step execution"),
            step_name=step.name,
        )

    def get_successful_results(self) -> list[CommandResult]:
        """Get only successful results.

        Returns:
            List of successful results
        """
        return [r for r in self.results if r.success]

    def get_failed_results(self) -> list[CommandResult]:
        """Get only failed results.

        Returns:
            List of failed results
        """
        return [r for r in self.results if not r.success]

    def all_successful(self) -> bool:
        """Check if all steps were successful.

        Returns:
            True if all steps succeeded
        """
        return all(r.success for r in self.results)


class TransactionalComposer(CommandComposer):
    """Command composer with transaction-like behavior."""

    def __init__(self) -> None:
        """Initialize transactional composer."""
        super().__init__()
        self.rollback_functions: dict[str, Callable] = {}

    def add_step_with_rollback(
        self,
        name: str,
        function: Callable,
        rollback_function: Callable,
        *args,
        **kwargs,
    ) -> "TransactionalComposer":
        """Add a step with rollback capability.

        Args:
            name: Step name
            function: Function to execute
            rollback_function: Function to call on rollback
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Self for chaining
        """
        self.add_step(name, function, *args, **kwargs)
        self.rollback_functions[name] = rollback_function
        return self

    def execute_with_rollback(self) -> list[CommandResult]:
        """Execute steps with automatic rollback on failure.

        Returns:
            List of results
        """
        results = self.execute()

        # Check if rollback is needed
        if not self.all_successful():
            logger.info("Executing rollback due to failures")
            self._rollback()

        return results

    def _rollback(self) -> None:
        """Rollback successful steps in reverse order."""
        successful = self.get_successful_results()

        for result in reversed(successful):
            if result.step_name in self.rollback_functions:
                try:
                    logger.debug(f"Rolling back step: {result.step_name}")
                    rollback_fn = self.rollback_functions[result.step_name]
                    rollback_fn(result.data)
                except Exception as e:
                    logger.error(f"Rollback failed for {result.step_name}: {e}")


# Example usage functions for common compositions
def compose_scene_workflow(
    read_func: Callable,
    validate_func: Callable,
    update_func: Callable,
    notify_func: Callable | None = None,
) -> CommandComposer:
    """Compose a scene editing workflow.

    Args:
        read_func: Function to read scene
        validate_func: Function to validate content
        update_func: Function to update scene
        notify_func: Optional function to notify on completion

    Returns:
        Configured command composer
    """
    composer = CommandComposer()
    composer.add_step("read", read_func, on_error="abort")
    composer.add_step("validate", validate_func, on_error="abort")
    composer.add_step("update", update_func, on_error="abort", retry_count=2)

    if notify_func:
        composer.add_step("notify", notify_func, on_error="continue")

    return composer
