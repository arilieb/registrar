# -*- encoding: utf-8 -*-
"""
registrar.core.authing module

"""

from urllib.parse import quote

from keri import kering
from keri.app.habbing import Habery, Hab
from keri.end import ending
from keri.help import helping
from keri.vdr.viring import Reger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class Authenticater:

    DefaultFields = ["Signify-Resource", "@method", "@path", "Signify-Timestamp"]

    def __init__(self, hby: Habery, hab: Hab, reger: Reger, schema: str):
        """Create Agent Authenticator for verifying requests and signing responses

        Parameters:
            hby (Habery): habitat of Agent for signing responses
            hab (Hab): habitat of Agent for signing responses
            reger (Reger): database of credentials and supporting artifacts
            schema (str): schema of controller for verifying credentials

        Returns:
              Authenicator:  the configured habery

        """
        self.hby = hby
        self.hab = hab
        self.reger = reger
        self.schema = schema

        self.authorized_watchers = dict()
        self._load_authorized_watchers()

    @staticmethod
    def resource(request):
        headers = request.headers
        if "SIGNIFY-RESOURCE" not in headers:
            raise ValueError("Missing signify resource header")

        return headers["SIGNIFY-RESOURCE"]

    def verify(self, request):
        resource = self.resource(request)

        if resource not in self.hby.kevers:
            raise kering.AuthNError("unknown or invalid controller")

        controller = (
            resource
            if resource not in self.authorized_watchers
            else self.authorized_watchers[resource]
        )
        if not self._verify_credential(controller):
            raise kering.AuthNError("invalid controller credential")

        headers = request.headers
        if "SIGNATURE-INPUT" not in headers or "SIGNATURE" not in headers:
            return False

        siginput = headers["SIGNATURE-INPUT"]
        if not siginput:
            return False
        signature = headers["SIGNATURE"]
        if not signature:
            return False

        inputs = ending.desiginput(siginput.encode("utf-8"))
        inputs = [i for i in inputs if i.name == "signify"]

        if not inputs:
            return False

        for inputage in inputs:
            items = []
            for field in inputage.fields:
                if field.startswith("@"):
                    if field == "@method":
                        items.append(f'"{field}": {request.method}')
                    elif field == "@path":
                        items.append(f'"{field}": {request.path}')

                else:
                    key = field.upper()
                    field = field.lower()
                    if key not in headers:
                        continue

                    value = ending.normalize(headers[key])
                    items.append(f'"{field}": {value}')

            values = [f"({' '.join(inputage.fields)})", f"created={inputage.created}"]
            if inputage.expires is not None:
                values.append(f"expires={inputage.expires}")
            if inputage.nonce is not None:
                values.append(f"nonce={inputage.nonce}")
            if inputage.keyid is not None:
                values.append(f"keyid={inputage.keyid}")
            if inputage.context is not None:
                values.append(f"context={inputage.context}")
            if inputage.alg is not None:
                values.append(f"alg={inputage.alg}")

            params = ";".join(values)

            items.append(f'"@signature-params: {params}"')
            ser = "\n".join(items).encode("utf-8")

            ckever = self.hby.kevers[resource]
            signages = ending.designature(signature)
            cig = signages[0].markers[inputage.name]
            if not ckever.verfers[0].verify(sig=cig.raw, ser=ser):
                raise kering.AuthNError(f"Signature for {inputage} invalid")

        return True

    def sign(self, headers, method, path, fields=None):
        """Generate and add Signature Input and Signature fields to headers

        Parameters:
            hab (Hab): The habitat of the agent that is replying to the request
            headers (dict): HTTP header to sign
            method (str): HTTP method name of request/response
            path (str): HTTP Query path of request/response
            fields (Optional[list]): Optional list of Signature Input fields to sign.

        Returns:
            headers (Hict): Modified headers with new Signature and Signature Input fields

        """

        if fields is None:
            fields = self.DefaultFields

        header, qsig = ending.siginput(
            "signify",
            method,
            path,
            headers,
            fields=fields,
            hab=self.hab,
            alg="ed25519",
            keyid=self.hab.pre,
        )
        headers.update(header)
        signage = ending.Signage(
            markers=dict(signify=qsig),
            indexed=False,
            signer=None,
            ordinal=None,
            digest=None,
            kind=None,
        )
        headers.update(ending.signature([signage]))

        return headers

    def _load_authorized_watchers(self):
        for (cid, aid, oid), observed in self.hby.db.obvs.getItemIter():
            if observed.enabled:
                self.authorized_watchers[aid] = cid

    def _verify_credential(self, controller):
        if not self.schema:
            return True

        saiders = self.reger.subjs.get(keys=(controller,))
        if not saiders:
            return False

        for saider in saiders:
            if (creder := self.reger.saved(keys=(saider.qb64,))) is not None:
                return creder.schema == self.schema

        return False


class SignatureValidationComponent(BaseHTTPMiddleware):
    """Validate Signature and Signature-Input header signatures"""

    def __init__(self, app, authn: Authenticater, allowed=None):
        """

        Parameters:
            app: Starlette application instance
            authn (Authenticater): Authenticator to validate signature headers on request
            allowed (list[str]): Paths that are not protected.

        """
        super().__init__(app)
        if allowed is None:
            allowed = []
        self.authn = authn
        self.allowed = allowed

    async def dispatch(self, request, call_next):
        """Process request to ensure has a valid signature from caid, then sign the response

        Parameters:
            request: Starlette Request object
            call_next: Function to call the next middleware/endpoint


        """

        # Check if path is in allowed list
        for path in self.allowed:
            if request.url.path.startswith(path):
                response = await call_next(request)
                return response

        # Store original path
        original_path = request.url.path
        quoted_path = quote(original_path)

        try:
            # Create a temporary object to pass to verify() that has the quoted path
            # The Authenticater expects request.path attribute
            class RequestAdapter:
                def __init__(self, req, path):
                    self.headers = req.headers
                    self.method = req.method
                    self.path = path

            adapted_request = RequestAdapter(request, quoted_path)

            # Use Authenticater to verify the signature on the request
            if self.authn.verify(adapted_request):
                resource = self.authn.resource(adapted_request)

                # Store agent in request state for endpoint handlers to use
                request.state.signer_aid = resource

                # Call the next middleware/endpoint
                response = await call_next(request)

                # Add signature headers to the response

                # Read response body
                body = b""
                async for chunk in response.body_iterator:  # type: ignore
                    body += chunk

                # Build headers dict from response
                headers = dict(response.headers)
                headers["Signify-Resource"] = self.authn.hab.pre
                headers["Signify-Timestamp"] = helping.nowIso8601()

                # Sign the headers
                signed_headers = self.authn.sign(headers, request.method, quoted_path)

                # Create new response with signed headers and body
                response = Response(
                    content=body,
                    status_code=response.status_code,
                    headers=signed_headers,
                    media_type=response.media_type,
                )

                return response

        except kering.AuthNError:
            pass
        except ValueError:
            pass

        # Return 401 Unauthorized if signature validation fails
        return Response(status_code=401)
