# -*- encoding: utf-8 -*-
"""
registrar.core.serving module

Functions and services for credential presentation and retrieval
"""

import asyncio
from datetime import datetime, timezone
from typing import Set

from keri import help
from keri.app.habbing import Habery
from keri.core import coring, parsing
from keri.vdr import credentialing, verifying

logger = help.ogler.getLogger()


class IPEXSocketListener:
    """
    Asyncio-based TCP socket listener that monitors new obvs entries.

    Listens on a TCP socket for connections. When a connection is received,
    reads all data from the connection, then checks hby.db.obvs for new entries
    (datetime > last_check) and calls add_watched_identifier for each new entry.
    """

    def __init__(
        self,
        hby: Habery,
        issuer: str,
        db,
        host: str = "127.0.0.1",
        port: int = 5621,
        poll_interval: float = 0.5,
    ):
        """
        Initialize the ObvsSocketListener.

        Args:
            hby: Habery instance for managing healthKERI accounts
            issuer: QB64 AID of the bootstrap issuer to who is authorized to issue KERIGuard credentials
            db: Database instance with watched_poll table
            host: Host address to bind to (default: 127.0.0.1)
            port: Port number to listen on (default: 5621)
            poll_interval: Timer interval for checking connections (default: 0.5 seconds)
        """
        self.hby = hby
        self.issuer = issuer
        self.rgy = credentialing.Regery(hby=self.hby, name=hby.name, base=hby.base)
        self.verifier = verifying.Verifier(hby=self.hby, reger=self.rgy.reger)
        self.psr = parsing.Parser(kvy=self.hby.kvy, tvy=self.rgy.tvy, vry=self.verifier)

        self.db = db
        self.host = host
        self.port = port
        self.poll_interval = poll_interval
        self._server = None
        self._task = None
        self._running = False
        self._connection_tasks: Set[asyncio.Task] = set()

    async def run(self):
        """
        Main asyncio loop that runs the TCP socket server.

        This method:
        1. Creates TCP socket server
        2. Accepts connections and processes them
        3. Handles cleanup on shutdown
        """
        self._running = True
        logger.info(f"ObvsSocketListener: Starting server on {self.host}:{self.port}")

        try:
            # Create TCP socket server
            self._server = await asyncio.start_server(
                self._handle_connection, host=self.host, port=self.port
            )

            logger.info(
                f"ObvsSocketListener: Server listening on {self.host}:{self.port}"
            )

            # Run server loop
            while self._running:
                await asyncio.sleep(self.poll_interval)

                # Clean up finished connection tasks
                self._connection_tasks = {
                    task for task in self._connection_tasks if not task.done()
                }

        except asyncio.CancelledError:
            logger.info("ObvsSocketListener: Task cancelled")
        except Exception as e:
            logger.exception(f"ObvsSocketListener: Error in run loop: {e}")
        finally:
            await self._cleanup()

        logger.info("ObvsSocketListener: Stopped")

    async def _cleanup(self):
        """
        Clean up server resources.
        """
        try:
            logger.info("ObvsSocketListener: Cleaning up...")

            # Close server
            if self._server:
                self._server.close()
                await self._server.wait_closed()
                logger.debug("ObvsSocketListener: Server closed")

            # Cancel all connection tasks
            if self._connection_tasks:
                logger.debug(
                    f"ObvsSocketListener: Cancelling {len(self._connection_tasks)} connection tasks"
                )
                for task in self._connection_tasks:
                    task.cancel()

                # Wait for all tasks to complete
                await asyncio.gather(*self._connection_tasks, return_exceptions=True)

        except Exception as e:
            logger.exception(f"ObvsSocketListener: Error during cleanup: {e}")

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """
        Handle a new connection by creating a task for it.

        Args:
            reader: StreamReader for reading from the connection
            writer: StreamWriter for writing to the connection
        """
        task = asyncio.create_task(self._process_connection(reader, writer))
        self._connection_tasks.add(task)

    async def _process_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """
        Process a single connection: read data and check obvs.

        Args:
            reader: StreamReader for reading from the connection
            writer: StreamWriter for writing to the connection
        """
        peer = writer.get_extra_info("peername")
        logger.info(f"ObvsSocketListener: New connection from {peer}")

        try:
            # Read all data from connection
            data = bytearray()
            while True:
                chunk = await reader.read(4096)
                if not chunk:
                    break
                data.extend(chunk)

            logger.debug(f"ObvsSocketListener: Received {len(data)} bytes from {peer}")

            # Check and add new obvs entries
            self.psr.parse(data)
            await self._check_and_add_obvs()

        except Exception as e:
            logger.exception(
                f"ObvsSocketListener: Error processing connection from {peer}: {e}"
            )
        finally:
            try:
                writer.close()
                await writer.wait_closed()
                logger.info(f"ObvsSocketListener: Connection from {peer} closed")
            except Exception as e:
                logger.exception(f"ObvsSocketListener: Error closing connection: {e}")

    async def _check_and_add_obvs(self):
        """
        Check hby.db.obvs for new entries and add them as watched identifiers.

        Filters obvs entries based on timestamp (datetime > last_check) and calls
        add_watched_identifier for each new entry.
        """
        try:
            # Check if we have necessary resources
            if not self.db:
                logger.warning(
                    "ObvsSocketListener: No DB available, skipping obvs check"
                )
                return

            if not self.db.watched_poll:
                logger.warning(
                    "ObvsSocketListener: watched_poll database not available"
                )
                return

            if not hasattr(self.hby.db, "obvs"):
                logger.warning("ObvsSocketListener: obvs database not available")
                return

            # Get last check timestamp from database
            last_check_dater = self.db.watched_poll.get(keys=("obvs_last",))

            if last_check_dater:
                last_check_dt = datetime.fromisoformat(last_check_dater.dts)
                logger.debug(f"ObvsSocketListener: Last check time: {last_check_dt}")
            else:
                # First check - use epoch
                last_check_dt = datetime(1970, 1, 1, tzinfo=timezone.utc)
                logger.debug(
                    f"ObvsSocketListener: First check, using epoch {last_check_dt}"
                )

            # Iterate through obvs entries
            new_count = 0
            success_count = 0
            error_count = 0

            for (cid, aid, oid), observed in self.hby.db.obvs.getItemIter():
                try:
                    # Check if entry has datetime and is newer than last check
                    if not hasattr(observed, "datetime") or not observed.datetime:
                        logger.debug(
                            f"ObvsSocketListener: Skipping obvs entry without datetime - oid={oid}"
                        )
                        continue

                    observed_dt = datetime.fromisoformat(observed.datetime)

                    if observed_dt > last_check_dt:
                        new_count += 1
                        logger.info(
                            f"ObvsSocketListener: New obvs entry - cid={cid}, aid={aid}, oid={oid}, "
                            f"name={getattr(observed, 'name', 'N/A')}, datetime={observed.datetime}"
                        )

                except Exception as e:
                    error_count += 1
                    logger.exception(
                        f"ObvsSocketListener: Error processing obvs entry (oid={oid}): {e}"
                    )
                    continue

            # Update last check timestamp to now
            now = datetime.now(timezone.utc)
            now_dater = coring.Dater(dts=now.isoformat())
            self.db.watched_poll.pin(keys=("obvs_last",), val=now_dater)
            logger.debug(f"ObvsSocketListener: Updated last check time to {now}")

            logger.info(
                f"ObvsSocketListener: Processed {new_count} new obvs entries - "
                f"success={success_count}, errors={error_count}"
            )

        except Exception as e:
            logger.exception(f"ObvsSocketListener: Error in _check_and_add_obvs: {e}")

    def start(self):
        """
        Start the socket listener as an asyncio task.

        Returns:
            The asyncio Task object
        """
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())
        return self._task

    def stop(self):
        """
        Stop the socket listener task.
        """
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
