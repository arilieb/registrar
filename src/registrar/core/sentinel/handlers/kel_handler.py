# -*- encoding: utf-8 -*-
"""
keriguard.app.sentinel.handlers.kel_handler

KEL (Key Event Log) event handler.
"""

from sentinel.framework import KELEvent
from keri import help

from ..config import SentinelConfig

logger = help.ogler.getLogger()


class KELHandler:
    """Handler for KEL events - manages peer configs based on key state changes."""

    def __init__(self, config: SentinelConfig):
        self.config = config

    async def process(self, event: KELEvent):
        """
        Process KEL event and update Wireguard configuration.

        When a KERI identifier's keys are rotated, we need to update
        the peer's public key in the Wireguard configuration.
        """
        logger.info(f"Processing KEL event for AID: {event.aid}")

        self.config.hby.psr.parse(event.data)

        # Check if this AID has a kever (key event registry)
        kever = self.config.hby.kevers.get(event.aid)
        if kever is None:
            logger.info(f"AID {event.aid} not found locally - may need to sync")
            return

        # Get current verification key
        current_verfer = kever.verfers[0]
        logger.debug(f"Current verfer for {event.aid}: {current_verfer.qb64}")

        logger.info(f"KEL event processed for {event.aid}")
