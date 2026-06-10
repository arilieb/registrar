# -*- encoding: utf-8 -*-
"""
registrar.app.registraring module

Functions and services for managing healthKERI account watchers
"""

from urllib.parse import urlparse

from keri.app import habbing, connecting
from keri.kering import ConfigurationError
from keri.vdr import credentialing

from sentinel.framework import register_handler
from sentinel.framework.basing import AppBaser
from sentinel.framework.watching import FileWatchingService

from registrar.core.apiing import RegistrarAPIService
from ..core.oobiing import Oobiery

# Handler imports
from ..core.sentinel.handler import RegistrarEventHandler
from ..core.sentinel.config import SentinelConfig


async def setup_local(name, alias, base, bran, issuer, schema, export_dir):
    """
    Setup local registrar services.

    Args:
        name: Database environment name
        alias: Human readable alias for the identifier
        base: Optional prefix to file location of KERI keystore
        bran: 22 character encryption passcode for keystore
        issuer: QB64 AID of the bootstrap issuer to who is authorized to issue KERIGuard credentials
        schema: JSON schema for validating KERIGuard credentials
        export_dir: Directory for exporting CESR files

    Returns:
        List of service instances
    """
    hby = habbing.Habery(name=name, base=base, bran=bran)
    rgy = credentialing.Regery(hby=hby, name=name, base=base)

    hab = hby.habByName(alias)
    if hab is None:
        hab = hby.makeHab(name=alias, transferable=False)

    ends = hab.endsFor(hab.pre)
    controller = ends.get("controller", {})
    locs = controller.get(hab.pre, {})
    http_location = locs.get("http", None)
    if not http_location:
        raise ConfigurationError(f"HTTP location not found for {alias}")

    parsed_url = urlparse(http_location)
    services = []
    # Add API service if hby is available
    if hby:
        # Create Organizer for contact management
        org = connecting.Organizer(hby=hby)

        api_service = RegistrarAPIService(
            hby=hby,
            hab=hab,
            org=org,
            issuer=issuer,
            rgy=rgy,
            host=parsed_url.hostname,
            port=parsed_url.port or 80,
            schema=schema,
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

    oobiery = Oobiery(hby=hby)
    services.append(oobiery)

    return services
