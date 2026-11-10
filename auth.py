"""Auth0 ServerClient initialization, token validation, and in-memory store implementations."""

import os
from typing import Any, Optional
import jwt
from dotenv import load_dotenv
from jwt import PyJWKClient
from auth0_server_python.auth_server import ServerClient
from auth0_server_python.auth_types import LogoutOptions, StartInteractiveLoginOptions
from auth0_server_python.store.abstract import StateStore, TransactionStore

# Load environment variables from .env
load_dotenv()

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_SECRET = os.getenv("AUTH0_SECRET")
AUTH0_REDIRECT_URI = os.getenv("AUTH0_REDIRECT_URI", "http://localhost:5000/callback")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE")

if not all([AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET, AUTH0_SECRET]):
    raise ValueError(
        "Missing required Auth0 environment variables. "
        "Please ensure AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET, "
        "and AUTH0_SECRET are set in your .env file."
    )


class InMemoryStateStore(StateStore):
    """Simple in-memory state store for development session storage."""

    def __init__(self, options: Optional[dict[str, Any]] = None):
        super().__init__(options or {})
        self._data: dict[str, Any] = {}

    def _get_key(self, identifier: str, options: Optional[dict[str, Any]] = None) -> str:
        if options and "session_id" in options and options["session_id"]:
            return f"{identifier}:{options['session_id']}"
        return identifier

    async def set(
        self,
        identifier: str,
        state: Any,
        remove_if_expires: bool = False,
        options: Optional[dict[str, Any]] = None,
    ) -> None:
        key = self._get_key(identifier, options)
        self._data[key] = state

    async def get(
        self,
        identifier: str,
        options: Optional[dict[str, Any]] = None,
    ) -> Optional[Any]:
        key = self._get_key(identifier, options)
        return self._data.get(key)

    async def delete(
        self,
        identifier: str,
        options: Optional[dict[str, Any]] = None,
    ) -> None:
        key = self._get_key(identifier, options)
        self._data.pop(key, None)

    async def delete_by_logout_token(
        self,
        claims: dict[str, Any],
        options: Optional[dict[str, Any]] = None,
    ) -> None:
        """Handle back-channel logout token claims in development."""
        sub = claims.get("sub")
        sid = claims.get("sid")
        to_delete = []
        for key, value in self._data.items():
            internal = (
                getattr(value, "internal", {})
                if hasattr(value, "internal")
                else (value.get("internal") if isinstance(value, dict) else {})
            )
            user = (
                getattr(value, "user", {})
                if hasattr(value, "user")
                else (value.get("user") if isinstance(value, dict) else {})
            )
            user_sub = (
                getattr(user, "sub", None)
                if hasattr(user, "sub")
                else (user.get("sub") if isinstance(user, dict) else None)
            )
            session_sid = internal.get("sid") if isinstance(internal, dict) else None
            if (sid and session_sid == sid) or (sub and user_sub == sub):
                to_delete.append(key)
        for key in to_delete:
            self._data.pop(key, None)


class InMemoryTransactionStore(TransactionStore):
    """Simple in-memory transaction store for PKCE login transactions."""

    def __init__(self, options: Optional[dict[str, Any]] = None):
        super().__init__(options or {})
        self._data: dict[str, Any] = {}

    async def set(
        self,
        identifier: str,
        state: Any,
        remove_if_expires: bool = False,
        options: Optional[dict[str, Any]] = None,
    ) -> None:
        self._data[identifier] = state

    async def get(
        self,
        identifier: str,
        options: Optional[dict[str, Any]] = None,
    ) -> Optional[Any]:
        return self._data.get(identifier)

    async def delete(
        self,
        identifier: str,
        options: Optional[dict[str, Any]] = None,
    ) -> None:
        self._data.pop(identifier, None)


# Instantiate stores
state_store = InMemoryStateStore({"secret": AUTH0_SECRET})
transaction_store = InMemoryTransactionStore({"secret": AUTH0_SECRET})

# Configure authorization parameters (request openid, profile, email scopes and audience if set)
default_auth_params: dict[str, Any] = {
    "scope": "openid profile email",
}
if AUTH0_AUDIENCE:
    default_auth_params["audience"] = AUTH0_AUDIENCE

# Initialize Auth0 ServerClient
auth0 = ServerClient(
    domain=AUTH0_DOMAIN,
    client_id=AUTH0_CLIENT_ID,
    client_secret=AUTH0_CLIENT_SECRET,
    secret=AUTH0_SECRET,
    redirect_uri=AUTH0_REDIRECT_URI,
    authorization_params=default_auth_params,
    state_store=state_store,
    transaction_store=transaction_store,
)

# Initialize PyJWKClient for tenant JWKS access token verification
_domain_normalized = (AUTH0_DOMAIN or "").replace("https://", "").replace("http://", "").strip("/")
_jwks_url = f"https://{_domain_normalized}/.well-known/jwks.json"
jwks_client = PyJWKClient(_jwks_url)


def verify_access_token(token: str) -> dict[str, Any]:
    """
    Validate the Auth0 access token (JWT, RS256, via the tenant's JWKS).

    Args:
        token: Raw Bearer JWT string from the Authorization header.

    Returns:
        Decoded payload dict containing claims (e.g. 'sub', 'aud', 'iss').

    Raises:
        ValueError: If the token is invalid, expired, or signature verification fails.
    """
    if not token:
        raise ValueError("Token is required.")

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        issuer = f"https://{_domain_normalized}/"
        decode_kwargs: dict[str, Any] = {
            "algorithms": ["RS256"],
            "issuer": issuer,
            "options": {"verify_exp": True},
            "leeway": 60,
        }
        if AUTH0_AUDIENCE:
            decode_kwargs["audience"] = AUTH0_AUDIENCE

        payload = jwt.decode(token, signing_key.key, **decode_kwargs)
        return payload
    except Exception as e:
        raise ValueError(f"Token validation failed: {str(e)}")


__all__ = [
    "auth0",
    "state_store",
    "transaction_store",
    "LogoutOptions",
    "StartInteractiveLoginOptions",
    "AUTH0_REDIRECT_URI",
    "AUTH0_AUDIENCE",
    "verify_access_token",
]
