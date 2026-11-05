"""Offline JWT security checks, using a disposable in-memory test key."""
from __future__ import annotations

import time
import unittest
from types import SimpleNamespace

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from auth0_verifier import (
    Auth0TokenVerifier, AUTH0_ISSUER, RESOURCE_URL, REQUIRED_PERMISSION
)

class TestAuth0Verifier(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.verifier = Auth0TokenVerifier()
        # Replace external JWKS lookup with the matching in-memory public key.
        self.verifier._jwks.get_signing_key_from_jwt = (
            lambda token: SimpleNamespace(key=self.key.public_key())
        )
        self.now = int(time.time())

    def make_token(self, **overrides):
        payload = {
            "iss": AUTH0_ISSUER,
            "aud": RESOURCE_URL,
            "iat": self.now,
            "exp": self.now + 120,
            "sub": "auth0|test-user",
            "azp": "trusted-test-client",
            "permissions": [REQUIRED_PERMISSION],
        }
        payload.update(overrides)
        return jwt.encode(payload, self.key, algorithm="RS256")

    async def test_valid_user_and_permission(self):
        value = await self.verifier.verify_token(self.make_token())
        self.assertIsNotNone(value)
        self.assertEqual(value.scopes, [REQUIRED_PERMISSION])
        self.assertEqual(value.resource, RESOURCE_URL)

    async def test_wrong_audience(self):
        self.assertIsNone(await self.verifier.verify_token(
            self.make_token(aud="https://other-api.example")))

    async def test_wrong_issuer(self):
        self.assertIsNone(await self.verifier.verify_token(
            self.make_token(iss="https://other-idp.example/")))

    async def test_expired(self):
        self.assertIsNone(await self.verifier.verify_token(
            self.make_token(exp=self.now - 120)))

    async def test_without_permission(self):
        self.assertIsNone(await self.verifier.verify_token(
            self.make_token(permissions=[])))

    async def test_wrong_permission_type(self):
        self.assertIsNone(await self.verifier.verify_token(
            self.make_token(permissions="read:trademarks")))

    async def test_no_client_identity(self):
        self.assertIsNone(await self.verifier.verify_token(
            self.make_token(azp="",client_id="")))

    async def test_modified_signature(self):
        forged = self.make_token()[:-8] + "abcdefgh"
        self.assertIsNone(await self.verifier.verify_token(forged))

    async def test_no_token(self):
        self.assertIsNone(await self.verifier.verify_token(""))

    async def test_external_key_retrieval_fails_closed(self):
        def offline(_token):
            raise ConnectionError("failed")
        self.verifier._jwks.get_signing_key_from_jwt = offline
        self.assertIsNone(await self.verifier.verify_token(self.make_token()))

if __name__ == "__main__":
    unittest.main()
