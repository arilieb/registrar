# -*- encoding: utf-8 -*-
"""
keriguard.app.sentinel.config

Configuration for Keriguard Sentinel handler.
"""

from dataclasses import dataclass

from keri.app.habbing import Habery


@dataclass
class SentinelConfig:
    """Configuration for Sentinel event handler."""

    # Sentinel framework settings
    export_dir: str  # Directory containing kel/, tel/, cred/
    poll_interval: float = 2.0  # Polling interval in seconds

    # KERI settings
    hby: Habery = None
