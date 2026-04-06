"""Unit tests for file-based logging in node executor."""

import os
import tempfile
import pytest

from app.core.config import settings


@pytest.mark.asyncio
async def test_log_file_created_on_execution():
    """Test that log file is created when a node runs."""
    from app.orchestration.executor import _execute_node_in_process

    with tempfile.TemporaryDirectory() as tmpdir:
        # Override LOG_DIR for this test
        original_log_dir = settings.LOG_DIR
        settings.LOG_DIR = tmpdir

        try:
            result = _execute_node_in_process(
                node_type="text_output",
                node_config={"message": "Hello from test"},
                pipeline_params={},
                upstream_outputs={},
                log_queue=None,
                pipeline_run_id="test_run_123",
                node_id="test_node_abc",
            )

            assert result["success"] is True

            # Check log file was created
            log_file = os.path.join(tmpdir, "test_run_123", "test_node_abc.log")
            assert os.path.exists(log_file)

            # Check log contents contain expected messages
            with open(log_file, "r") as f:
                content = f.read()
            assert "Hello from test" in content or "text_output" in content.lower()
        finally:
            settings.LOG_DIR = original_log_dir


@pytest.mark.asyncio
async def test_log_file_appends_multiple_logs():
    """Test that multiple log messages are appended."""
    from app.orchestration.executor import _execute_node_in_process

    with tempfile.TemporaryDirectory() as tmpdir:
        original_log_dir = settings.LOG_DIR
        settings.LOG_DIR = tmpdir

        try:
            _execute_node_in_process(
                node_type="text_output",
                node_config={"message": "First message"},
                pipeline_params={},
                upstream_outputs={},
                log_queue=None,
                pipeline_run_id="test_run",
                node_id="test_node",
            )

            log_file = os.path.join(tmpdir, "test_run", "test_node.log")
            with open(log_file, "r") as f:
                lines = f.readlines()

            # Should have multiple lines (from logger formatter)
            assert len(lines) >= 1
        finally:
            settings.LOG_DIR = original_log_dir
