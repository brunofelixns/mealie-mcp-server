"""Personal, out-of-band bearer authentication using FastMCP's public verifier."""

import hashlib
import hmac

from fastmcp.server.auth import AccessToken, TokenVerifier


class PersonalTokenVerifier(TokenVerifier):
    def __init__(self, token: str) -> None:
        super().__init__()
        self._digest = hashlib.sha256(token.encode("utf-8")).digest()

    async def verify_token(self, token: str) -> AccessToken | None:
        supplied = hashlib.sha256(token.encode("utf-8")).digest()
        if not hmac.compare_digest(self._digest, supplied):
            return None
        return AccessToken(token=token, client_id="personal", scopes=[])
