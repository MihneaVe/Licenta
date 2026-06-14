"""Auth0 access-token validation for the write/compute API endpoints.

Defence-in-depth on top of the database row-level security: when AUTH0_DOMAIN
and AUTH0_AUDIENCE are configured, ``require_auth`` verifies the incoming
``Authorization: Bearer <token>`` as an Auth0 access token - an RS256 JWT whose
signature is checked against the tenant's JWKS, with audience and issuer
asserted. When they are not configured (local/dev, the docker ``localdb``
profile), the dependency is a no-op so the app runs without an Auth0 tenant.

Apply it per-route with ``dependencies=[Depends(require_auth)]``.
"""

import logging

from fastapi import HTTPException, Request, status

from .config import AUTH0_ALGORITHMS, AUTH0_AUDIENCE, AUTH0_DOMAIN, AUTH_ENABLED

logger = logging.getLogger(__name__)

# Lazily built so importing this module never triggers a network call and the
# `jwt` dependency is only needed when auth is actually enabled.
_jwks_client = None


def _jwks():
    global _jwks_client
    if _jwks_client is None:
        import jwt  # PyJWT
        _jwks_client = jwt.PyJWKClient(f"https://{AUTH0_DOMAIN}/.well-known/jwks.json")
    return _jwks_client


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_auth(request: Request):
    """FastAPI dependency: enforce a valid Auth0 JWT when auth is configured."""
    if not AUTH_ENABLED:
        return None

    import jwt  # PyJWT

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise _unauthorized("Missing bearer token")
    token = header.split(" ", 1)[1].strip()

    try:
        signing_key = _jwks().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=AUTH0_ALGORITHMS,
            audience=AUTH0_AUDIENCE,
            issuer=f"https://{AUTH0_DOMAIN}/",
        )
    except Exception as exc:  # noqa: BLE001 - any failure → 401
        logger.warning("Auth0 token rejected: %s", exc)
        raise _unauthorized("Invalid or expired token")
