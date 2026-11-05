"""Auth0 RS256 access-token verification for the EUIPO MCP resource server.

Never accept ID tokens, unsigned tokens, tokens for other APIs or callers
without the explicit RBAC permission. On any verification error fail closed.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken, TokenVerifier

AUTH0_ISSUER = os.environ["AUTH0_ISSUER"].rstrip("/") + "/"
RESOURCE_URL = os.environ["MCP_RESOURCE_URL"].rstrip("/")
REQUIRED_PERMISSION = "read:trademarks"

if not AUTH0_ISSUER.startswith("https://") or not RESOURCE_URL.startswith("https://"):
    raise RuntimeError("OAuth issuer and MCP resource must use HTTPS")

class Auth0TokenVerifier(TokenVerifier):
    """Verify Auth0-issued JWTs against the tenant JWKS and this API's audience."""

    def __init__(self) -> None:
        # All JWKS requests go to our fixed tenant, never to a token-supplied URL.
        self._jwks = PyJWKClient(
            f"{AUTH0_ISSUER}.well-known/jwks.json",
            cache_jwk_set=True,
            lifespan=300,
            timeout=5,
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        if not isinstance(token, str) or not 30 < len(token) <= 8192:
            return None
        try:
            signing_key = await asyncio.to_thread(
                self._jwks.get_signing_key_from_jwt, token
            )
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=AUTH0_ISSUER,
                audience=RESOURCE_URL,
                options={"require": ["iss", "aud", "exp", "iat", "sub"]},
                leeway=30,
            )
            perms = claims.get("permissions")
            if not isinstance(perms, list) or REQUIRED_PERMISSION not in perms:
                return None
            subject = claims.get("sub")
            client_id = claims.get("azp") or claims.get("client_id")
            expiry = claims.get("exp")
            if (
                not isinstance(subject, str) or not subject
                or not isinstance(client_id, str) or not client_id
                or not isinstance(expiry, int)
            ):
                return None
            return AccessToken(
                token=token,
                client_id=client_id,
                scopes=[REQUIRED_PERMISSION],
                expires_at=expiry,
                resource=RESOURCE_URL,
                subject=subject,
            )
        except Exception:
            # Invalid signature, expired JWT, unknown key, DNS failure, etc.
            # Never log, echo or fall back to anonymous access.
            return None
