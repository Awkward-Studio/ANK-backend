from time import time
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from rest_framework.exceptions import PermissionDenied

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from Staff.google_login import verified_identity
from Staff.models import User


START = "/api/auth/google/login/start/"
COMPLETE = "/api/auth/google/login/complete/"
NONCE = "n" * 43
VERIFIER = "v" * 64
CLAIMS = {
    "email": "staff@anewknot.com",
    "email_verified": True,
    "hd": "anewknot.com",
    "sub": "12345",
}


@override_settings(
    USE_JWT=True,
    GOOGLE_LOGIN_DOMAIN="anewknot.com",
    GOOGLE_CALENDAR_CLIENT_ID="test.apps.googleusercontent.com",
    GOOGLE_CALENDAR_CLIENT_SECRET="test-secret",
    GOOGLE_CALENDAR_APP_ORIGIN="https://rsvp.anewknot.com",
)
class GoogleLoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(CLAIMS["email"], role="admin")
        self.addCleanup(self.client.logout)

    def test_start_requests_identity_only(self):
        self.assertEqual(self.client.get(START).json(), {"enabled": True})
        response = self.client.post(START, {
            "state": "s" * 43, "nonce": NONCE, "challenge": "c" * 43,
        })
        self.assertEqual(response.status_code, 200)
        query = parse_qs(urlsplit(response.json()["authorization_url"]).query)
        self.assertEqual(query["scope"], ["openid email"])
        self.assertEqual(query["hd"], ["anewknot.com"])
        self.assertEqual(query["redirect_uri"], ["https://rsvp.anewknot.com/api/auth/google/callback"])
        self.assertNotIn("client_secret", query)

    @override_settings(GOOGLE_LOGIN_DOMAIN="")
    def test_feature_is_disabled_without_workspace_domain(self):
        self.assertEqual(self.client.get(START).json(), {"enabled": False})
        self.assertEqual(self.client.post(COMPLETE).status_code, 503)

    @patch("Staff.google_login.token_request", return_value={"id_token": "provider-token"})
    @patch("Staff.google_login.verified_identity", return_value=CLAIMS)
    def test_matching_workspace_account_gets_existing_role(self, verify, exchange):
        response = self.client.post(COMPLETE, {
            "code": "provider-code", "nonce": NONCE, "verifier": VERIFIER,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["role"], "admin")
        self.assertEqual(response.json()["user"]["id"], str(self.user.pk))
        self.assertTrue(response.json()["tokens"]["access"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.google_login_subject, CLAIMS["sub"])
        verify.assert_called_once_with("provider-token", NONCE)
        self.assertEqual(exchange.call_args.kwargs["code_verifier"], VERIFIER)

    @patch("Staff.google_login.token_request", return_value={"id_token": "provider-token"})
    @patch("Staff.google_login.verified_identity")
    def test_personal_unknown_and_reassigned_accounts_are_denied(self, verify, _exchange):
        self.user.google_login_subject = "original-account"
        self.user.save(update_fields=["google_login_subject"])
        for changes in (
            {"hd": "gmail.com"},
            {"email_verified": False},
            {"email": "unknown@anewknot.com"},
            {},
        ):
            with self.subTest(changes=changes):
                verify.return_value = {**CLAIMS, **changes}
                response = self.client.post(COMPLETE, {
                    "code": "provider-code", "nonce": NONCE, "verifier": VERIFIER,
                })
                self.assertEqual(response.status_code, 403)
        self.assertEqual(User.objects.count(), 1)


    def test_id_token_requires_google_audience_and_matching_nonce(self):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = int(time())
        claims = {
            **CLAIMS,
            "iss": "https://accounts.google.com",
            "aud": "test.apps.googleusercontent.com",
            "iat": now,
            "exp": now + 60,
            "nonce": NONCE,
        }
        with patch(
            "Staff.google_login.google_keys.get_signing_key_from_jwt",
            return_value=SimpleNamespace(key=key.public_key()),
        ):
            token = jwt.encode(claims, key, algorithm="RS256")
            self.assertEqual(verified_identity(token, NONCE)["sub"], CLAIMS["sub"])
            with self.assertRaises(PermissionDenied):
                verified_identity(token, "x" * 43)
            wrong_audience = jwt.encode({**claims, "aud": "different-client"}, key, algorithm="RS256")
            with self.assertRaises(PermissionDenied):
                verified_identity(wrong_audience, NONCE)
