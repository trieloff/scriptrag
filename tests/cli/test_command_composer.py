"""Tests for command composition utilities."""

from scriptrag.cli.utils.command_composer import (
    CommandComposer,
    CommandResult,
    CommandStep,
    TransactionalComposer,
    compose_scene_workflow,
)


class TestCommandComposer:
    """Test command composition."""

    def test_simple_composition(self):
        """Test simple command composition."""
        composer = CommandComposer()

        # Track execution order
        execution_order = []

        def step1():
            execution_order.append("step1")
            return "result1"

        def step2():
            execution_order.append("step2")
            return "result2"

        composer.add_step("step1", step1)
        composer.add_step("step2", step2)

        results = composer.execute()

        assert len(results) == 2
        assert results[0].success is True
        assert results[0].data == "result1"
        assert results[1].success is True
        assert results[1].data == "result2"
        assert execution_order == ["step1", "step2"]

    def test_composition_with_args(self):
        """Test composition with arguments."""
        composer = CommandComposer()

        def add(a, b):
            return a + b

        def multiply(x, factor=2):
            return x * factor

        composer.add_step("add", add, 3, 4)
        composer.add_step("multiply", multiply, 5, factor=3)

        results = composer.execute()

        assert results[0].data == 7
        assert results[1].data == 15

    def test_error_handling_abort(self):
        """Test error handling with abort strategy."""
        composer = CommandComposer()

        execution_order = []

        def step1():
            execution_order.append("step1")
            return "ok"

        def step2():
            execution_order.append("step2")
            raise ValueError("Test error")

        def step3():
            execution_order.append("step3")
            return "should not execute"

        composer.add_step("step1", step1)
        composer.add_step("step2", step2, on_error="abort")
        composer.add_step("step3", step3)

        results = composer.execute()

        assert len(results) == 2  # Only 2 steps executed
        assert results[0].success is True
        assert results[1].success is False
        assert isinstance(results[1].error, ValueError)
        assert execution_order == ["step1", "step2"]  # step3 not executed

    def test_error_handling_continue(self):
        """Test error handling with continue strategy."""
        composer = CommandComposer()

        execution_order = []

        def step1():
            execution_order.append("step1")
            return "ok"

        def step2():
            execution_order.append("step2")
            raise ValueError("Test error")

        def step3():
            execution_order.append("step3")
            return "continues"

        composer.add_step("step1", step1)
        composer.add_step("step2", step2, on_error="continue")
        composer.add_step("step3", step3)

        results = composer.execute()

        assert len(results) == 3  # All steps executed
        assert results[0].success is True
        assert results[1].success is False
        assert results[2].success is True
        assert results[2].data == "continues"
        assert execution_order == ["step1", "step2", "step3"]

    def test_retry_logic(self):
        """Test retry logic on failure."""
        composer = CommandComposer()

        attempt_count = 0

        def flaky_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        composer.add_step("flaky", flaky_function, retry_count=2)

        results = composer.execute()

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].data == "success"
        assert attempt_count == 3  # Initial + 2 retries

    def test_retry_exhausted(self):
        """Test when retries are exhausted."""
        composer = CommandComposer()

        def always_fails():
            raise ConnectionError("Permanent failure")

        composer.add_step("failing", always_fails, retry_count=2)

        results = composer.execute()

        assert len(results) == 1
        assert results[0].success is False
        assert isinstance(results[0].error, ConnectionError)

    def test_get_successful_results(self):
        """Test getting only successful results."""
        composer = CommandComposer()

        composer.add_step("success1", lambda: "ok1")
        composer.add_step("failure", lambda: 1 / 0, on_error="continue")
        composer.add_step("success2", lambda: "ok2")

        composer.execute()

        successful = composer.get_successful_results()
        assert len(successful) == 2
        assert successful[0].data == "ok1"
        assert successful[1].data == "ok2"

    def test_get_failed_results(self):
        """Test getting only failed results."""
        composer = CommandComposer()

        composer.add_step("success", lambda: "ok")
        composer.add_step("failure1", lambda: 1 / 0, on_error="continue")
        composer.add_step("failure2", lambda: None.missing, on_error="continue")

        composer.execute()

        failed = composer.get_failed_results()
        assert len(failed) == 2
        assert isinstance(failed[0].error, ZeroDivisionError)
        assert isinstance(failed[1].error, AttributeError)

    def test_all_successful(self):
        """Test checking if all steps were successful."""
        composer1 = CommandComposer()
        composer1.add_step("step1", lambda: "ok1")
        composer1.add_step("step2", lambda: "ok2")
        composer1.execute()
        assert composer1.all_successful() is True

        composer2 = CommandComposer()
        composer2.add_step("step1", lambda: "ok")
        composer2.add_step("step2", lambda: 1 / 0, on_error="continue")
        composer2.execute()
        assert composer2.all_successful() is False


class TestTransactionalComposer:
    """Test transactional command composition."""

    def test_successful_transaction(self):
        """Test successful transaction without rollback."""
        composer = TransactionalComposer()

        state = {"value": 0}

        def increment():
            state["value"] += 1
            return state["value"]

        def decrement(data):
            state["value"] -= 1

        composer.add_step_with_rollback("inc1", increment, decrement)
        composer.add_step_with_rollback("inc2", increment, decrement)

        results = composer.execute_with_rollback()

        assert len(results) == 2
        assert all(r.success for r in results)
        assert state["value"] == 2  # No rollback

    def test_transaction_with_rollback(self):
        """Test transaction with rollback on failure."""
        composer = TransactionalComposer()

        state = {"operations": []}

        def operation1():
            state["operations"].append("op1")
            return "op1_data"

        def rollback1(data):
            state["operations"].append(f"rollback_{data}")

        def operation2():
            state["operations"].append("op2")
            return "op2_data"

        def rollback2(data):
            state["operations"].append(f"rollback_{data}")

        def operation3():
            state["operations"].append("op3")
            raise ValueError("Operation failed")

        composer.add_step_with_rollback("op1", operation1, rollback1)
        composer.add_step_with_rollback("op2", operation2, rollback2)
        composer.add_step("op3", operation3)  # No rollback for this

        results = composer.execute_with_rollback()

        # Check that rollback was executed in reverse order
        assert state["operations"] == [
            "op1",
            "op2",
            "op3",
            "rollback_op2_data",
            "rollback_op1_data",
        ]
        assert not composer.all_successful()

    def test_rollback_failure_handling(self):
        """Test handling of rollback failures."""
        composer = TransactionalComposer()

        executed = []

        def operation():
            executed.append("operation")
            return "data"

        def failing_rollback(data):
            executed.append("rollback_attempt")
            raise RuntimeError("Rollback failed")

        def failing_operation():
            executed.append("failing_op")
            raise ValueError("Operation failed")

        composer.add_step_with_rollback("op1", operation, failing_rollback)
        composer.add_step("op2", failing_operation)

        results = composer.execute_with_rollback()

        # Rollback should be attempted despite failure
        assert "operation" in executed
        assert "failing_op" in executed
        assert "rollback_attempt" in executed


class TestCommandStep:
    """Test CommandStep dataclass."""

    def test_command_step_initialization(self):
        """Test CommandStep initialization."""
        step = CommandStep(
            name="test",
            function=lambda: "result",
            args=(1, 2),
            kwargs={"key": "value"},
        )

        assert step.name == "test"
        assert step.args == (1, 2)
        assert step.kwargs == {"key": "value"}
        assert step.on_error == "abort"
        assert step.retry_count == 0

    def test_command_step_defaults(self):
        """Test CommandStep default values."""
        step = CommandStep(
            name="test",
            function=lambda: "result",
        )

        assert step.args == ()
        assert step.kwargs == {}
        assert step.on_error == "abort"
        assert step.retry_count == 0


class TestCommandResult:
    """Test CommandResult dataclass."""

    def test_successful_result(self):
        """Test successful command result."""
        result = CommandResult(
            success=True,
            data={"key": "value"},
            step_name="test_step",
        )

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None
        assert result.step_name == "test_step"

    def test_failed_result(self):
        """Test failed command result."""
        error = ValueError("Test error")
        result = CommandResult(
            success=False,
            error=error,
            step_name="failing_step",
        )

        assert result.success is False
        assert result.data is None
        assert result.error == error
        assert result.step_name == "failing_step"


class TestComposeSceneWorkflow:
    """Test scene workflow composition helper."""

    def test_compose_scene_workflow(self):
        """Test composing a scene workflow."""
        executed = []

        def read():
            executed.append("read")
            return "scene_content"

        def validate():
            executed.append("validate")
            return True

        def update():
            executed.append("update")
            return "updated"

        def notify():
            executed.append("notify")
            return "notified"

        composer = compose_scene_workflow(read, validate, update, notify)

        assert len(composer.steps) == 4
        assert composer.steps[0].name == "read"
        assert composer.steps[1].name == "validate"
        assert composer.steps[2].name == "update"
        assert composer.steps[3].name == "notify"

        # Update step should have retry
        assert composer.steps[2].retry_count == 2

        # Notify should continue on error
        assert composer.steps[3].on_error == "continue"

    def test_compose_scene_workflow_without_notify(self):
        """Test composing workflow without notification."""
        composer = compose_scene_workflow(
            lambda: "read",
            lambda: "validate",
            lambda: "update",
            None,  # No notification
        )

        assert len(composer.steps) == 3
        assert all(s.name != "notify" for s in composer.steps)
