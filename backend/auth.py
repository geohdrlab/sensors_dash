from __future__ import annotations

import secrets
from dataclasses import dataclass

from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


@dataclass(frozen=True)
class AuthContext:
    authenticated: bool


async def authenticate_request(
    request: Request, supplied: str | None = Security(api_key_header)
) -> AuthContext:
    settings = request.app.state.settings
    authenticated = bool(
        settings.api_key
        and supplied
        and secrets.compare_digest(supplied, settings.api_key)
    )
    if settings.require_api_key and not authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"detail": "A valid API key is required", "code": "invalid_api_key"},
        )
    return AuthContext(authenticated=authenticated)
