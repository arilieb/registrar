# -*- encoding: utf-8 -*-
"""
keriguard.app.sentinel.handler

Main Sentinel EventHandler for Keriguard that responds to all three event types.
"""

# Sentinel framework imports
from sentinel.framework import EventHandler, KELEvent, TELEvent, CredentialEvent

from keri import help

# Handler-specific imports
from .config import SentinelConfig
from .handlers.kel_handler import KELHandler

logger = help.ogler.getLogger()


class RegistrarEventHandler(EventHandler):
    """
    Keriguard Sentinel event handler responding to all three event types.

    This handler monitors KERI events and manages Wireguard configurations:
    - KEL events: Create/update peer configs based on key state changes
    - TEL events: Manage transaction-based peer authorizations
    - Credential events: Handle credential-based peer access control
    """

    def __init__(self, config: SentinelConfig):
        """Initialize the handler with configuration."""
        self.config = config

        # Create specialized handlers for each event type
        self.kel_handler = KELHandler(config)

        logger.info("Registrar Sentinel handler initialized")

    async def on_kel(self, event: KELEvent):
        """
        Handle Key Event Log (KEL) events.

        KEL events represent changes to KERI key states. When an AID's keys
        are rotated or updated, we need to update the corresponding peer's
        public key in the Wireguard configuration.

        Args:
            event: KELEvent containing AID, file path, CESR data, and optional hby
        """
        try:
            logger.info(f"KEL event received for AID: {event.aid}")
            logger.debug(f"  File: {event.filepath}")
            logger.debug(f"  Data size: {len(event.data)} bytes")

            # Delegate to specialized KEL handler
            await self.kel_handler.process(event)

        except Exception as e:
            logger.error(f"Error processing KEL event for {event.aid}: {e}")
            # Don't re-raise - allow other handlers to continue

    async def on_tel(self, event: TELEvent):
        """
        Handle Transaction Event Log (TEL) events.

        TEL events represent transaction-based state changes. These could be
        used to track peer authorizations, bandwidth allocations, or other
        transaction-based peer management.

        Args:
            event: TELEvent containing AID, file path, CESR data, and optional hby
        """
        try:
            logger.info(f"TEL event received for AID: {event.aid}")
            logger.debug(f"  File: {event.filepath}")

            # Delegate to specialized TEL handler
            await self.tel_handler.process(event)

        except Exception as e:
            logger.error(f"Error processing TEL event for {event.aid}: {e}")

    async def on_credential(self, event: CredentialEvent):
        """
        Handle Credential events.

        Credential events represent credential issuance, revocation, or updates.
        These can be used for credential-based peer access control - only peers
        with valid credentials can be added to configurations.

        Args:
            event: CredentialEvent containing AID, file path, CESR data, and optional hby
        """
        try:
            logger.info(f"Credential event received for AID: {event.aid}")
            logger.debug(f"  File: {event.filepath}")

            # Delegate to specialized credential handler
            await self.cred_handler.process(event)

        except Exception as e:
            logger.error(f"Error processing credential event for {event.aid}: {e}")
