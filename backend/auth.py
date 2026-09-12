"""Supabase is the identity authority; plans never come from JWT user metadata."""
from dataclasses import dataclass
from uuid import UUID
import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from .config import config
from .db import database, Profile, AdminMember
from .security import rate_limit

bearer = HTTPBearer(auto_error=False)
jwks = jwt.PyJWKClient(config.supabase_url + '/auth/v1/.well-known/jwks.json', cache_jwk_set=True, lifespan=300, timeout=8)
auth_http = httpx.Client(timeout=10, limits=httpx.Limits(max_connections=30, max_keepalive_connections=10))


@dataclass(frozen=True)
class Identity:
    id: str
    email: str
    name: str


def require_user(request: Request, credential: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credential or credential.scheme.lower() != 'bearer':
        raise HTTPException(401, 'Sign in to continue.', headers={'WWW-Authenticate': 'Bearer'})
    token = credential.credentials
    if len(token) > 12000:
        raise HTTPException(401, 'Invalid session.')
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get('alg')
        if alg in ('ES256', 'RS256'):
            key = jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=[alg], audience='authenticated', issuer=config.supabase_url + '/auth/v1',
                                options={'require': ['exp', 'iat', 'sub', 'aud', 'iss']}, leeway=10)
            if claims.get('role') != 'authenticated' or claims.get('is_anonymous'):
                raise ValueError('A registered account is required')
            user_id = str(UUID(claims['sub']))
            email = claims.get('email', '')
            name = str(claims.get('user_metadata', {}).get('display_name', 'Trader'))[:100]
        elif alg == 'HS256':
            # Legacy shared-signing-key projects are verified by Supabase, never a frontend-supplied secret.
            claims = None
        else:
            raise ValueError('Unsupported token algorithm')
        # Live identity checks on mutations also reject deleted accounts and blocked users.
        if alg == 'HS256' or request.method not in ('GET', 'HEAD') or request.url.path.startswith('/api/admin'):
            result = auth_http.get(config.supabase_url + '/auth/v1/user', headers={'apikey': config.supabase_key, 'Authorization': 'Bearer ' + token})
            if result.status_code >= 500:
                raise HTTPException(503, 'Sign-in verification is temporarily unavailable.')
            if result.status_code != 200:
                raise ValueError('Invalid session')
            user = result.json()
            if user.get('is_anonymous') or not user.get('email_confirmed_at'):
                raise ValueError('Verify your email before continuing')
            user_id = str(UUID(user['id']))
            email = user.get('email', '')
            name = str(user.get('user_metadata', {}).get('display_name', 'Trader'))[:100]
        identity = Identity(user_id, email, name)
    except HTTPException:
        raise
    except (httpx.HTTPError, jwt.PyJWKClientConnectionError):
        raise HTTPException(503, 'Sign-in verification is temporarily unavailable.')
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise HTTPException(401, 'Your session has expired. Please sign in again.', headers={'WWW-Authenticate': 'Bearer'})
    with database(identity.id) as db:
        from .runtime_settings import settings
        product = settings(db)
        profile = db.get(Profile, identity.id)
        if profile and profile.suspended:
            raise HTTPException(403, 'This account is suspended. Contact support for assistance.')
        member = db.get(AdminMember, identity.id)
        if product.maintenance_enabled and not (member and member.active):
            raise HTTPException(503, product.maintenance_message)
        rate_limit(db, 'user:' + identity.id, product.api_requests_per_minute, 60)
    request.state.identity = identity
    return identity


def get_db(identity: Identity = Depends(require_user)):
    with database(identity.id) as db:
        yield db
