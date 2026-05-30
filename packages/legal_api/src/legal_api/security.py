"""Authentication for the SaaS surface.

v1 alpha ships API-key auth: each org has one or more rotatable
`X-Anchor-API-Key` strings. Future surfaces add OIDC for human users
(Auth0/Cognito) behind the same `RequestPrincipal` dependency.

The token → principal lookup is pluggable so tests don't have to set
up a real auth backend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from fastapi import Depends, Header, HTTPException, Request, status


@dataclass
class RequestPrincipal:
    org_id: str
    api_key_id: str
    scopes: frozenset[str] = field(default_factory=frozenset)


class ApiKeyResolver(Protocol):
    def __call__(self, raw_key: str) -> RequestPrincipal | None: ...


@dataclass
class InMemoryApiKeyResolver:
    """Maps a raw API key → RequestPrincipal. Tests preload it."""

    by_key: dict[str, RequestPrincipal] = field(default_factory=dict)

    def __call__(self, raw_key: str) -> RequestPrincipal | None:
        return self.by_key.get(raw_key)


def require_principal(
    request: Request,
    x_anchor_api_key: str | None = Header(default=None, alias="X-Anchor-API-Key"),
) -> RequestPrincipal:
    """FastAPI dependency: returns the authenticated principal or 401."""
    resolver: ApiKeyResolver = request.app.state.api_key_resolver
    if not x_anchor_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Anchor-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    principal = resolver(x_anchor_api_key)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return principal


def require_scope(scope: str) -> Callable[[RequestPrincipal], RequestPrincipal]:
    """Factory: returns a dependency that 403s when the principal
    doesn't carry `scope`."""

    def _checker(
        principal: RequestPrincipal = Depends(require_principal),
    ) -> RequestPrincipal:
        if scope not in principal.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"missing scope: {scope}",
            )
        return principal

    return _checker
