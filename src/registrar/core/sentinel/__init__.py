# -*- encoding: utf-8 -*-
"""
keriguard.app.sentinel module

Sentinel framework handler for KERI event monitoring.

This module requires the 'sentinel-handler' extra:
    pip install keriguard[sentinel-handler]
"""

# ruff: noqa: F401 E402


def _check_sentinel_dependencies():
    """Verify Sentinel dependencies are installed."""
    try:
        import sentinel
    except ImportError:
        raise ImportError(
            "Sentinel framework not installed.\n"
            "Install with: pip install keriguard[sentinel-handler]"
        )


# Check dependencies at import time
_check_sentinel_dependencies()

# Now safe to import handler components
from .handler import RegistrarEventHandler

__all__ = ["RegistrarEventHandler"]
