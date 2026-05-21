# -*- encoding: utf-8 -*-
"""
registrar.app.registraring module

Functions and services for managing healthKERI account watchers
"""

from keri.app import habbing
from keri.vdr import credentialing

from sentinel.framework import register_handler
from sentinel.framework.basing import AppBaser
from sentinel.framework.watching import FileWatchingService

from registrar.core.apiing import RegistrarAPIService
from registrar.core.serving import IPEXSocketListener

# Handler imports
from ..core.sentinel.handler import RegistrarEventHandler
from ..core.sentinel.config import SentinelConfig


async def setup_local(name, alias, base, bran, port, export_dir, http_port=8080):
    """
    Setup local registrar services.

    Args:
        name: Database environment name
        alias: Human readable alias for the identifier
        base: Optional prefix to file location of KERI keystore
        bran: 22 character encryption passcode for keystore
        port: Port for IPEXSocketListener
        export_dir: Directory for exporting CESR files
        http_port: Port for API service (default: 8080)

    Returns:
        List of service instances
    """
    hby = habbing.Habery(name=name, base=base, bran=bran)
    rgy = credentialing.Regery(hby=hby, name=name, base=base)

    hab = hby.habByName(alias)
    if hab is None:
        hab = hby.makeHab(name=alias, transferable=False)

    db = None

    services = []

    # Add IPEXSocketListener if hby and db are available
    if hby and db:
        ipex_listener = IPEXSocketListener(hby=hby, db=db, host="127.0.0.1", port=port)
        services.append(ipex_listener)

    # Add API service if hby is available
    if hby:
        api_service = RegistrarAPIService(
            hby=hby, rgy=rgy, host="127.0.0.1", port=http_port
        )
        services.append(api_service)

    # Create configuration
    poll_interval = 3.0
    config = SentinelConfig(
        hby=hby,
        export_dir=str(export_dir),
        poll_interval=poll_interval,
    )

    handler = RegistrarEventHandler(config)
    register_handler(handler)

    sentinel_db = AppBaser(name=hby.name, headDirPath=export_dir)
    service = FileWatchingService(
        export_dir=export_dir,
        poll_interval=poll_interval,
        hby=hby,
        rgy=rgy,
        db=sentinel_db,
    )
    services.append(service)

    return services
