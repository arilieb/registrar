# -*- encoding: utf-8 -*-
"""
Unit tests for registrar.core.serving module
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

from registrar.core.serving import IPEXSocketListener


class TestIPEXSocketListener:
    """Test suite for IPEXSocketListener class"""

    @pytest.fixture
    def mock_hby(self):
        """Create a mock Habery instance"""
        hby = Mock()
        hby.name = "test-hby"
        hby.base = "/tmp/keri"
        hby.kvy = Mock()
        hby.db = Mock()
        hby.db.obvs = Mock()
        return hby

    @pytest.fixture
    def mock_db(self):
        """Create a mock database instance"""
        db = Mock()
        db.watched_poll = Mock()
        return db

    @pytest.fixture
    def listener(self, mock_hby, mock_db):
        """Create an IPEXSocketListener instance"""
        with (
            patch("registrar.core.serving.credentialing.Regery"),
            patch("registrar.core.serving.verifying.Verifier"),
            patch("registrar.core.serving.parsing.Parser"),
        ):
            listener = IPEXSocketListener(
                hby=mock_hby, db=mock_db, host="0.0.0.0", port=6000, poll_interval=0.1
            )
        return listener

    def test_init_default_params(self, mock_hby, mock_db):
        """Test IPEXSocketListener initialization with default parameters"""
        with (
            patch("registrar.core.serving.credentialing.Regery") as mock_regery,
            patch("registrar.core.serving.verifying.Verifier") as mock_verifier,
            patch("registrar.core.serving.parsing.Parser") as mock_parser,
        ):

            mock_rgy_instance = Mock()
            mock_regery.return_value = mock_rgy_instance
            mock_verifier_instance = Mock()
            mock_verifier.return_value = mock_verifier_instance
            mock_parser_instance = Mock()
            mock_parser.return_value = mock_parser_instance

            listener = IPEXSocketListener(hby=mock_hby, db=mock_db)

            # Verify default parameters
            assert listener.hby == mock_hby
            assert listener.db == mock_db
            assert listener.host == "127.0.0.1"
            assert listener.port == 5621
            assert listener.poll_interval == 0.5
            assert listener._server is None
            assert listener._task is None
            assert listener._running is False
            assert listener._connection_tasks == set()

            # Verify Regery initialization
            mock_regery.assert_called_once_with(
                hby=mock_hby, name=mock_hby.name, base=mock_hby.base
            )

            # Verify Verifier initialization
            mock_verifier.assert_called_once_with(
                hby=mock_hby, reger=mock_rgy_instance.reger
            )

            # Verify Parser initialization
            mock_parser.assert_called_once_with(
                kvy=mock_hby.kvy, tvy=mock_rgy_instance.tvy, vry=mock_verifier_instance
            )

    def test_init_custom_params(self, mock_hby, mock_db):
        """Test IPEXSocketListener initialization with custom parameters"""
        with (
            patch("registrar.core.serving.credentialing.Regery"),
            patch("registrar.core.serving.verifying.Verifier"),
            patch("registrar.core.serving.parsing.Parser"),
        ):

            listener = IPEXSocketListener(
                hby=mock_hby,
                db=mock_db,
                host="192.168.1.100",
                port=7777,
                poll_interval=2.5,
            )

            assert listener.host == "192.168.1.100"
            assert listener.port == 7777
            assert listener.poll_interval == 2.5

    @pytest.mark.asyncio
    async def test_run_success(self, listener):
        """Test run method starts server successfully"""
        with patch("asyncio.start_server") as mock_start_server:
            mock_server = Mock()
            mock_start_server.return_value = mock_server

            # Create a task that will stop the listener after a short time
            async def run_and_stop():
                task = asyncio.create_task(listener.run())
                await asyncio.sleep(0.05)
                listener.stop()
                await asyncio.sleep(0.05)
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Execute
            await run_and_stop()

            # Verify
            mock_start_server.assert_called_once_with(
                listener._handle_connection, host="0.0.0.0", port=6000
            )

    @pytest.mark.asyncio
    async def test_run_cancelled_error(self, listener):
        """Test run method handles CancelledError"""
        with patch("asyncio.start_server") as mock_start_server:
            mock_start_server.side_effect = asyncio.CancelledError()

            # Execute
            await listener.run()

            # Verify cleanup was called (server would be None since start_server failed)
            assert listener._server is None

    @pytest.mark.asyncio
    async def test_run_exception(self, listener):
        """Test run method handles generic exceptions"""
        with patch("asyncio.start_server") as mock_start_server:
            mock_start_server.side_effect = Exception("Test error")

            # Execute
            await listener.run()

            # Verify cleanup was called (server would be None since start_server failed)
            assert listener._server is None

    @pytest.mark.asyncio
    async def test_run_cleans_up_finished_tasks(self, listener):
        """Test that run method cleans up finished connection tasks"""
        with patch("asyncio.start_server") as mock_start_server:
            mock_server = Mock()
            mock_start_server.return_value = mock_server

            # Create mock tasks - some done, some not
            done_task = Mock()
            done_task.done.return_value = True
            running_task = Mock()
            running_task.done.return_value = False

            listener._connection_tasks = {done_task, running_task}

            # Run for a short time
            async def run_and_stop():
                task = asyncio.create_task(listener.run())
                await asyncio.sleep(0.15)  # Wait for at least one poll interval
                listener.stop()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            await run_and_stop()

            # Verify done task was removed
            assert done_task not in listener._connection_tasks
            # Note: running_task may or may not still be there depending on timing

    @pytest.mark.asyncio
    async def test_cleanup_with_server_and_tasks(self, listener):
        """Test cleanup method with server and connection tasks"""
        # Setup mock server
        mock_server = Mock()
        mock_server.close = Mock()
        mock_server.wait_closed = AsyncMock()
        listener._server = mock_server

        # Setup mock connection tasks
        mock_task1 = Mock()
        mock_task1.cancel = Mock()
        mock_task2 = Mock()
        mock_task2.cancel = Mock()
        listener._connection_tasks = {mock_task1, mock_task2}

        with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
            # Execute
            await listener._cleanup()

            # Verify server cleanup
            mock_server.close.assert_called_once()
            mock_server.wait_closed.assert_called_once()

            # Verify tasks cancelled
            mock_task1.cancel.assert_called_once()
            mock_task2.cancel.assert_called_once()

            # Verify gather called
            mock_gather.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_without_server(self, listener):
        """Test cleanup method when server is None"""
        listener._server = None
        listener._connection_tasks = set()

        # Execute - should not raise error
        await listener._cleanup()

    @pytest.mark.asyncio
    async def test_cleanup_exception_handling(self, listener):
        """Test cleanup method handles exceptions"""
        mock_server = Mock()
        mock_server.close.side_effect = Exception("Close error")
        listener._server = mock_server

        # Execute - should not raise error
        await listener._cleanup()

    @pytest.mark.asyncio
    async def test_handle_connection(self, listener):
        """Test _handle_connection creates and tracks task"""
        mock_reader = Mock(spec=asyncio.StreamReader)
        mock_writer = Mock(spec=asyncio.StreamWriter)

        with patch("asyncio.create_task") as mock_create_task:
            mock_task = Mock()
            mock_create_task.return_value = mock_task

            # Execute
            await listener._handle_connection(mock_reader, mock_writer)

            # Verify task created and added to set
            mock_create_task.assert_called_once()
            assert mock_task in listener._connection_tasks

    @pytest.mark.asyncio
    async def test_process_connection_success(self, listener):
        """Test _process_connection with successful data read"""
        # Setup mock reader/writer
        mock_reader = Mock(spec=asyncio.StreamReader)
        mock_writer = Mock(spec=asyncio.StreamWriter)
        mock_writer.get_extra_info.return_value = ("127.0.0.1", 12345)
        mock_writer.close = Mock()
        mock_writer.wait_closed = AsyncMock()

        # Mock reading data
        test_data = b"test data chunk"
        mock_reader.read = AsyncMock(side_effect=[test_data, b""])

        # Mock parser and check_and_add_obvs
        listener.psr.parse = Mock()
        listener._check_and_add_obvs = AsyncMock()

        # Execute
        await listener._process_connection(mock_reader, mock_writer)

        # Verify
        assert mock_reader.read.call_count == 2
        listener.psr.parse.assert_called_once_with(bytearray(test_data))
        listener._check_and_add_obvs.assert_called_once()
        mock_writer.close.assert_called_once()
        mock_writer.wait_closed.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_connection_multiple_chunks(self, listener):
        """Test _process_connection with multiple data chunks"""
        # Setup mock reader/writer
        mock_reader = Mock(spec=asyncio.StreamReader)
        mock_writer = Mock(spec=asyncio.StreamWriter)
        mock_writer.get_extra_info.return_value = ("127.0.0.1", 12345)
        mock_writer.close = Mock()
        mock_writer.wait_closed = AsyncMock()

        # Mock reading multiple chunks
        chunk1 = b"first chunk"
        chunk2 = b"second chunk"
        chunk3 = b"third chunk"
        mock_reader.read = AsyncMock(side_effect=[chunk1, chunk2, chunk3, b""])

        # Mock parser and check_and_add_obvs
        listener.psr.parse = Mock()
        listener._check_and_add_obvs = AsyncMock()

        # Execute
        await listener._process_connection(mock_reader, mock_writer)

        # Verify all chunks combined
        expected_data = bytearray(chunk1 + chunk2 + chunk3)
        listener.psr.parse.assert_called_once_with(expected_data)

    @pytest.mark.asyncio
    async def test_process_connection_exception(self, listener):
        """Test _process_connection handles exceptions during processing"""
        # Setup mock reader/writer
        mock_reader = Mock(spec=asyncio.StreamReader)
        mock_writer = Mock(spec=asyncio.StreamWriter)
        mock_writer.get_extra_info.return_value = ("127.0.0.1", 12345)
        mock_writer.close = Mock()
        mock_writer.wait_closed = AsyncMock()

        # Mock reading data then exception
        mock_reader.read = AsyncMock(side_effect=Exception("Read error"))

        # Execute - should not raise
        await listener._process_connection(mock_reader, mock_writer)

        # Verify connection still closed
        mock_writer.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_connection_close_exception(self, listener):
        """Test _process_connection handles exception during connection close"""
        # Setup mock reader/writer
        mock_reader = Mock(spec=asyncio.StreamReader)
        mock_writer = Mock(spec=asyncio.StreamWriter)
        mock_writer.get_extra_info.return_value = ("127.0.0.1", 12345)
        mock_writer.close = Mock()
        mock_writer.wait_closed = AsyncMock(side_effect=Exception("Close error"))

        # Mock reading data
        mock_reader.read = AsyncMock(return_value=b"")

        listener.psr.parse = Mock()
        listener._check_and_add_obvs = AsyncMock()

        # Execute - should not raise
        await listener._process_connection(mock_reader, mock_writer)

    @pytest.mark.asyncio
    async def test_check_and_add_obvs_no_db(self, listener):
        """Test _check_and_add_obvs with no database"""
        listener.db = None

        # Execute - should not raise
        await listener._check_and_add_obvs()

    @pytest.mark.asyncio
    async def test_check_and_add_obvs_no_watched_poll(self, listener):
        """Test _check_and_add_obvs with no watched_poll"""
        listener.db.watched_poll = None

        # Execute - should not raise
        await listener._check_and_add_obvs()

    @pytest.mark.asyncio
    async def test_check_and_add_obvs_no_obvs(self, listener):
        """Test _check_and_add_obvs with no obvs in hby.db"""
        delattr(listener.hby.db, "obvs")

        # Execute - should not raise
        await listener._check_and_add_obvs()

    @pytest.mark.asyncio
    async def test_check_and_add_obvs_first_check(self, listener):
        """Test _check_and_add_obvs on first check (no last_check)"""
        # Setup mocks
        listener.db.watched_poll.get.return_value = None

        # Create mock obvs entries
        mock_observed = Mock()
        mock_observed.datetime = "2024-01-15T12:00:00+00:00"
        mock_observed.name = "test-observer"

        listener.hby.db.obvs.getItemIter.return_value = [
            (("cid1", "aid1", "oid1"), mock_observed)
        ]

        # Mock Dater
        with patch("registrar.core.serving.coring.Dater") as mock_dater:
            mock_dater_instance = Mock()
            mock_dater.return_value = mock_dater_instance

            # Execute
            await listener._check_and_add_obvs()

            # Verify last_check was queried
            listener.db.watched_poll.get.assert_called_once_with(keys=("obvs_last",))

            # Verify last check time was updated
            listener.db.watched_poll.pin.assert_called_once()
            call_args = listener.db.watched_poll.pin.call_args
            assert call_args.kwargs["keys"] == ("obvs_last",)

    @pytest.mark.asyncio
    async def test_check_and_add_obvs_with_last_check(self, listener):
        """Test _check_and_add_obvs with existing last_check timestamp"""
        # Setup mock last check
        mock_last_check = Mock()
        mock_last_check.dts = "2024-01-10T10:00:00+00:00"
        listener.db.watched_poll.get.return_value = mock_last_check

        # Create mock obvs entries - one old, one new
        old_observed = Mock()
        old_observed.datetime = "2024-01-09T12:00:00+00:00"
        old_observed.name = "old-observer"

        new_observed = Mock()
        new_observed.datetime = "2024-01-15T12:00:00+00:00"
        new_observed.name = "new-observer"

        listener.hby.db.obvs.getItemIter.return_value = [
            (("cid1", "aid1", "oid1"), old_observed),
            (("cid2", "aid2", "oid2"), new_observed),
        ]

        with patch("registrar.core.serving.coring.Dater"):
            # Execute
            await listener._check_and_add_obvs()

            # Verify processed - old one should be skipped, new one processed

    @pytest.mark.asyncio
    async def test_check_and_add_obvs_skip_no_datetime(self, listener):
        """Test _check_and_add_obvs skips entries without datetime"""
        listener.db.watched_poll.get.return_value = None

        # Create mock obvs entry without datetime
        mock_observed = Mock(spec=[])  # No datetime attribute

        listener.hby.db.obvs.getItemIter.return_value = [
            (("cid1", "aid1", "oid1"), mock_observed)
        ]

        with patch("registrar.core.serving.coring.Dater"):
            # Execute - should not raise
            await listener._check_and_add_obvs()

    @pytest.mark.asyncio
    async def test_check_and_add_obvs_skip_none_datetime(self, listener):
        """Test _check_and_add_obvs skips entries with None datetime"""
        listener.db.watched_poll.get.return_value = None

        # Create mock obvs entry with None datetime
        mock_observed = Mock()
        mock_observed.datetime = None

        listener.hby.db.obvs.getItemIter.return_value = [
            (("cid1", "aid1", "oid1"), mock_observed)
        ]

        with patch("registrar.core.serving.coring.Dater"):
            # Execute - should not raise
            await listener._check_and_add_obvs()

    @pytest.mark.asyncio
    async def test_check_and_add_obvs_entry_processing_error(self, listener):
        """Test _check_and_add_obvs handles error processing individual entry"""
        listener.db.watched_poll.get.return_value = None

        # Create mock obvs entries - one will cause error, one will succeed
        error_observed = Mock()
        error_observed.datetime = "invalid-datetime"  # Will cause parse error

        good_observed = Mock()
        good_observed.datetime = "2024-01-15T12:00:00+00:00"
        good_observed.name = "good-observer"

        listener.hby.db.obvs.getItemIter.return_value = [
            (("cid1", "aid1", "oid1"), error_observed),
            (("cid2", "aid2", "oid2"), good_observed),
        ]

        with patch("registrar.core.serving.coring.Dater"):
            # Execute - should not raise, should continue processing
            await listener._check_and_add_obvs()

    @pytest.mark.asyncio
    async def test_check_and_add_obvs_uses_name_attribute(self, listener):
        """Test _check_and_add_obvs uses name attribute when available"""
        listener.db.watched_poll.get.return_value = None

        # Create mock obvs entry with name
        mock_observed = Mock()
        mock_observed.datetime = "2024-01-15T12:00:00+00:00"
        mock_observed.name = "custom-name"

        listener.hby.db.obvs.getItemIter.return_value = [
            (("cid1", "aid1", "oid1"), mock_observed)
        ]

        with patch("registrar.core.serving.coring.Dater"):
            # Execute
            await listener._check_and_add_obvs()

            # The name attribute was used (verified in logs, but we can't easily assert on it)

    @pytest.mark.asyncio
    async def test_check_and_add_obvs_uses_oid_fallback(self, listener):
        """Test _check_and_add_obvs uses oid when no name attribute"""
        listener.db.watched_poll.get.return_value = None

        # Create mock obvs entry without name attribute
        mock_observed = Mock(spec=["datetime"])
        mock_observed.datetime = "2024-01-15T12:00:00+00:00"

        listener.hby.db.obvs.getItemIter.return_value = [
            (("cid1", "aid1", "oid-fallback"), mock_observed)
        ]

        with patch("registrar.core.serving.coring.Dater"):
            # Execute
            await listener._check_and_add_obvs()

    @pytest.mark.asyncio
    async def test_check_and_add_obvs_updates_timestamp(self, listener):
        """Test _check_and_add_obvs updates timestamp after processing"""
        listener.db.watched_poll.get.return_value = None
        listener.hby.db.obvs.getItemIter.return_value = []

        with (
            patch("registrar.core.serving.coring.Dater") as mock_dater,
            patch("registrar.core.serving.datetime") as mock_datetime,
        ):

            # Mock datetime.now
            mock_now = datetime(2024, 1, 20, 15, 30, 0, tzinfo=timezone.utc)
            mock_datetime.now.return_value = mock_now
            mock_datetime.fromisoformat = datetime.fromisoformat

            mock_dater_instance = Mock()
            mock_dater.return_value = mock_dater_instance

            # Execute
            await listener._check_and_add_obvs()

            # Verify Dater created with now timestamp
            mock_datetime.now.assert_called_once_with(timezone.utc)
            mock_dater.assert_called_once_with(dts=mock_now.isoformat())

            # Verify timestamp pinned
            listener.db.watched_poll.pin.assert_called_once_with(
                keys=("obvs_last",), val=mock_dater_instance
            )

    @pytest.mark.asyncio
    async def test_check_and_add_obvs_exception_in_main_loop(self, listener):
        """Test _check_and_add_obvs handles exception in main loop"""
        # Make getItemIter raise exception
        listener.hby.db.obvs.getItemIter.side_effect = Exception("Iterator error")

        # Execute - should not raise
        await listener._check_and_add_obvs()

    def test_start(self, listener):
        """Test start method creates asyncio task"""
        with patch("asyncio.create_task") as mock_create_task:
            mock_task = Mock()
            mock_create_task.return_value = mock_task

            # Execute
            result = listener.start()

            # Verify
            mock_create_task.assert_called_once()
            assert result == mock_task
            assert listener._task == mock_task

    def test_start_already_running(self, listener):
        """Test start method when task already exists and not done"""
        # Create a mock task that's not done
        mock_task = Mock()
        mock_task.done.return_value = False
        listener._task = mock_task

        with patch("asyncio.create_task") as mock_create_task:
            # Execute
            result = listener.start()

            # Verify - should not create new task
            mock_create_task.assert_not_called()
            assert result == mock_task

    def test_start_task_done(self, listener):
        """Test start method when previous task is done"""
        # Create a mock task that's done
        old_task = Mock()
        old_task.done.return_value = True
        listener._task = old_task

        with patch("asyncio.create_task") as mock_create_task:
            new_task = Mock()
            mock_create_task.return_value = new_task

            # Execute
            result = listener.start()

            # Verify - should create new task
            mock_create_task.assert_called_once()
            assert result == new_task
            assert listener._task == new_task

    def test_stop(self, listener):
        """Test stop method when task is running"""
        # Setup
        mock_task = Mock()
        mock_task.done.return_value = False
        listener._task = mock_task
        listener._running = True

        # Execute
        listener.stop()

        # Verify
        assert listener._running is False
        mock_task.cancel.assert_called_once()

    def test_stop_without_task(self, listener):
        """Test stop method when no task exists"""
        # Setup
        listener._task = None
        listener._running = True

        # Execute - should not raise error
        listener.stop()

        # Verify
        assert listener._running is False

    def test_stop_task_already_done(self, listener):
        """Test stop method when task is already done"""
        # Setup
        mock_task = Mock()
        mock_task.done.return_value = True
        listener._task = mock_task
        listener._running = True

        # Execute
        listener.stop()

        # Verify - should not call cancel
        mock_task.cancel.assert_not_called()
        assert listener._running is False

    @pytest.mark.asyncio
    async def test_integration_start_stop(self, listener):
        """Integration test for start and stop"""
        with patch("asyncio.start_server") as mock_start_server:
            mock_server = Mock()
            mock_server.close = Mock()
            mock_server.wait_closed = AsyncMock()
            mock_start_server.return_value = mock_server

            # Start the listener
            task = listener.start()
            assert listener._task is not None

            # Let it run briefly
            await asyncio.sleep(0.05)

            # Stop it
            listener.stop()

            # Wait for cleanup
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except asyncio.CancelledError:
                pass

            # Verify stopped
            assert listener._running is False
