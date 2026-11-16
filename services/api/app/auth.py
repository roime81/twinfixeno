import os
from functools import lru_cache
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt import PyJWKClient

bearer = HTTPBearer(auto_error=False)

@lru_cache
def jwks_client():
    url = os.getenv("KEYCLOAK_JWKS_URL", "http://localhost:8081/realms/twinfixeno/protocol/openid-connect/certs")
    return PyJWKClient(url, cache_keys=True)

def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if os.getenv("AUTH_REQUIRED", "true").lower() not in ("1", "true", "yes"):
        return {"sub": "local-development", "preferred_username": "local-development", "roles": ["twinfixeno-admin"]}
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required", headers={"WWW-Authenticate": "Bearer"})
    issuer = os.getenv("KEYCLOAK_ISSUER", "http://localhost:8081/realms/twinfixeno")
    audience = os.getenv("JWT_AUDIENCE", "twinfixeno-api")
    try:
        signing_key = jwks_client().get_signing_key_from_jwt(credentials.credentials)
        claims = jwt.decode(credentials.credentials, signing_key.key, algorithms=["RS256"], audience=audience, issuer=issuer)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"}) from exc
    realm_access = claims.get("realm_access", {})
    return {
        "sub": claims.get("sub"),
        "preferred_username": claims.get("preferred_username"),
        "roles": realm_access.get("roles", []),
        "claims": claims,
    }
