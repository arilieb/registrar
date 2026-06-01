# -*- encoding: utf-8 -*-
"""
registrar.core.apiing module

API service for serving registry, TEL, and credential endpoints
"""

import asyncio

from hypercorn.asyncio import serve
from hypercorn.config import Config
from keri import help, kering
from keri.app import signing
from keri.app.habbing import Habery, Hab
from keri.core import serdering, parsing, coring, routing
from keri.peer import exchanging
from keri.vdr import verifying
from keri.vdr.credentialing import Regery
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from registrar.core.authing import Authenticater, SignatureValidationComponent

logger = help.ogler.getLogger()


class RegistrarAPIService:
    """
    Asyncio-based API service using Starlette and Hypercorn.

    Provides three GET endpoints:
    - /registry: Returns registry data
    - /tel: Returns transaction event log data
    - /credential: Returns credential data
    """

    def __init__(
        self,
        hby: Habery,
        hab: Hab,
        rgy: Regery,
        issuer: str,
        schema: str,
        host: str = "127.0.0.1",
        port: int = 8080,
    ):
        """
        Initialize the RegistrarAPIService.

        Args:
            hby: Habery instance for managing healthKERI accounts
            hab: Hab instance for signing responses
            rgy: Regery instance for managing credentials
            issuer: Issuer DID for credential issuance
            schema: Schema for credential issuance
            host: Host address to bind to (default: 127.0.0.1)
            port: Port number to listen on (default: 8080)
        """
        self.hby = hby
        self.hab = hab
        self.rgy = rgy
        self.issuer = issuer

        self.rtr = routing.Router()
        self.rvy = routing.Revery(db=self.hby.db, rtr=self.rtr)
        self.hby.kvy.registerReplyRoutes(router=self.rtr)

        self.verifier = verifying.Verifier(hby=self.hby, reger=self.rgy.reger)
        self.exc = exchanging.Exchanger(hby=self.hby, handlers=[])
        self.credential_psr = parsing.Parser(
            kvy=self.hby.kvy, tvy=self.rgy.tvy, vry=self.verifier
        )
        self.external_psr = parsing.Parser(kvy=self.hby.kvy, rvy=self.rvy, exc=self.exc)

        self.exc.addHandler(
            IPEXGrantHandler(hby=self.hby, psr=self.credential_psr, issuer=issuer)
        )

        self.host = host
        self.port = port
        self._task = None
        self._running = False
        self._shutdown_trigger = None

        # Create Starlette app with routes
        self.app = Starlette(
            debug=False,
            routes=[
                Route("/", self.parse, methods=["PUT"]),
                Route("/registry/{regi}", self.get_registry, methods=["GET"]),
                Route("/tel/{said}", self.get_tel, methods=["GET"]),
                Route("/credential/{said}", self.get_credential, methods=["GET"]),
            ],
        )

        authn = Authenticater(hby=hby, hab=hab, reger=self.rgy.reger, schema=schema)
        self.app.add_middleware(
            SignatureValidationComponent,  # type: ignore
            authn=authn,
            allowed=["/"],  # Paths that don't require signatures
        )

    async def parse(self, request: Request):
        """
        Handle GET /registry endpoint.

        Returns:
            Response with registry datd
        """
        data = await request.body()
        self.external_psr.parse(data)

        self.rvy.processEscrowReply()
        self.exc.processEscrow()
        self.credential_psr.kvy.processEscrows()
        self.rgy.tvy.processEscrows()
        self.verifier.processEscrows()

        return Response(status_code=204)

    async def get_registry(self, request):
        """
        Handle GET /registry endpoint.

        Returns:
            Response with registry datd
        """
        regi = request.path_params.get("regi")
        if regi is None:
            return JSONResponse(
                {"message": "Credential transaction event log not found"},
                status_code=404,
            )

        try:
            registry_tel = self.output_tel(regi)
            if not registry_tel:
                return JSONResponse(
                    {"message": "Registry transaction event log not found"},
                    status_code=404,
                )
        except kering.MissingEntryError:
            return JSONResponse(
                {"message": "Registry transaction event log not found"}, status_code=404
            )

        return Response(
            content=registry_tel, media_type="application/cesr", status_code=200
        )

    async def get_tel(self, request):
        """
        Handle GET /tel endpoint.

        Returns:
            Response with TEL data
        """
        said = request.path_params.get("said")
        if said is None:
            return JSONResponse(
                {"message": "Credential transaction event log not found"},
                status_code=404,
            )

        registry_tel = self.output_tel(said)
        if not registry_tel:
            return JSONResponse(
                {"message": "Credential transaction event log not found"},
                status_code=404,
            )

        return Response(
            content=registry_tel, media_type="application/cesr", status_code=200
        )

    async def get_credential(self, request):
        """
        Handle GET /credential endpoint.

        Returns:
            Response with credential data and optional credential and registry transaction event logs
        """

        said = request.path_params.get("said")
        if said is None:
            return JSONResponse(
                {"message": "Credential not found, no said"}, status_code=404
            )

        registry = request.query_params.get("registry", False)
        tel = request.query_params.get("tel", False)
        chains = request.query_params.get("chains", False)

        try:
            out = self.output_cred(said, tel, registry, chains)
            if not out:
                return JSONResponse(
                    {"message": f"Credential not found for {said}"}, status_code=404
                )

            return Response(content=out, media_type="application/cesr", status_code=200)
        except kering.MissingEntryError as e:
            logger.error(f"Credential not found for said {said}: {e}")
            return JSONResponse(
                {"message": f"Credential not found for said {said}"}, status_code=404
            )

    async def run(self):
        """
        Main asyncio loop that runs the Hypercorn ASGI server.

        This method:
        1. Creates Hypercorn config
        2. Sets up shutdown trigger
        3. Serves the Starlette app
        4. Handles cleanup on shutdown
        """
        self._running = True
        logger.info(
            f"RegistrarAPIService: Starting API server on {self.host}:{self.port}"
        )

        try:
            # Create Hypercorn config
            config = Config()
            config.bind = [f"{self.host}:{self.port}"]
            config.accesslog = "-"  # Log to stdout
            config.errorlog = "-"  # Log to stderr

            # Create shutdown trigger
            self._shutdown_trigger = asyncio.Event()

            # Run Hypercorn server
            await serve(self.app, config, shutdown_trigger=self._shutdown_trigger.wait)  # type: ignore

        except asyncio.CancelledError:
            logger.info("RegistrarAPIService: Task cancelled")
        except Exception as e:
            logger.exception(f"RegistrarAPIService: Error in run loop: {e}")
        finally:
            self._running = False

        logger.info("RegistrarAPIService: Stopped")

    def start(self):
        """
        Start the API service as an asyncio task.

        Returns:
            The asyncio Task object
        """
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())
        return self._task

    def stop(self):
        """
        Stop the API service task.
        """
        self._running = False
        if self._shutdown_trigger:
            self._shutdown_trigger.set()
        if self._task and not self._task.done():
            self._task.cancel()

    def output_tel(self, regk):
        out = bytearray()
        for msg in self.rgy.reger.clonePreIter(pre=regk):
            serder = serdering.SerderKERI(raw=msg)
            atc = msg[serder.size :]
            out.extend(serder.raw)
            out.extend(atc)

        return bytes(out)

    def output_cred(self, said, tel, registry, chains):
        creder, *_ = self.rgy.reger.cloneCred(said=said)

        out = bytearray()
        if registry and creder.regi is not None:
            out.extend(self.output_tel(creder.regi))

        if tel:
            out.extend(self.output_tel(creder.said))

        if chains:
            chains = creder.edge if creder.edge is not None else {}
            saids = []
            for key, source in chains.items():
                if key == "d":
                    continue

                if not isinstance(source, dict):
                    continue

                saids.append(source["n"])

            for said in saids:
                out.extend(self.output_cred(said, tel, registry, chains))

        prefixer, seqner, saider = self.rgy.reger.cancs.get(keys=(creder.said,))
        out.extend(signing.serialize(creder, prefixer, seqner, saider))

        return bytes(out)


class IPEXGrantHandler:
    resource = "/ipex/grant"

    def __init__(self, hby, psr, issuer):
        """
        Initialize the IPEXGrantHandler with the given parameters.

        Parameters:
            hby (Habery): Habitat instance for signing responses
            psr (Psr): Proof Service Registry instance for managing credentials
            issuer (str): Issuer DID for credential issuance
        """
        self.hby = hby
        self.psr = psr
        self.issuer = issuer

    def handle(self, serder, attachments=None):
        """Do route specific processsing of IPEX protocol exn messages

        Parameters:
            serder (Serder): Serder of the IPEX protocol exn message
            attachments (list): list of tuples of pather, CESR SAD path attachments to the exn event

        """
        grant, pathed = exchanging.cloneMessage(self.hby, serder.said)
        embeds = serder.ked["e"]

        creder = serdering.SerderACDC(sad=embeds["acdc"])
        if creder.issuer != self.issuer:
            logger.info(
                f"ACDC issuer {creder.issuer} does not match expected issuer {self.issuer} on {serder.said}"
            )
            return

        logger.info(
            f"Processing IPEX grant for {serder.said} with valid credential issued from {creder.issuer}"
        )

        # Lets get the latest KEL and Registry if needed
        for label in ("anc", "iss", "acdc"):
            ked = embeds[label]
            sadder = coring.Sadder(ked=ked)
            ims = bytearray(sadder.raw) + pathed[label]
            self.psr.parseOne(ims=ims)
