import os
from functools import lru_cache

import jwt
from django.conf import settings
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import User


@lru_cache(maxsize=8)
def get_jwks_client(jwks_url):
    return jwt.PyJWKClient(jwks_url)


class SupabaseJWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        authorization = get_authorization_header(request).split()
        if not authorization:
            return None
        if len(authorization) != 2 or authorization[0].lower() != b"bearer":
            raise AuthenticationFailed("Authorization must use a Bearer token.")

        token = authorization[1].decode("utf-8")
        jwks_url = os.environ.get("SUPABASE_JWKS_URL")
        if not jwks_url:
            supabase_url = os.environ.get("SUPABASE_URL")
            if supabase_url:
                jwks_url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        if not jwks_url:
            raise AuthenticationFailed("Supabase JWT verification is not configured.")

        try:
            signing_key = get_jwks_client(jwks_url).get_signing_key_from_jwt(token)
            issuer = os.environ.get("SUPABASE_JWT_ISSUER")
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                audience="authenticated",
                issuer=issuer if issuer else None,
                options={"verify_iss": bool(issuer)},
            )
        except (jwt.PyJWTError, ValueError) as exc:
            raise AuthenticationFailed("Invalid or expired Supabase token.") from exc

        user_id = claims.get("sub")
        if not user_id:
            raise AuthenticationFailed("Supabase token has no user identity.")
        try:
            user, _ = User.objects.get_or_create(
                id=user_id,
                defaults={"email": claims.get("email", "")},
            )
        except (TypeError, ValueError) as exc:
            raise AuthenticationFailed("Supabase token has an invalid user identity.") from exc
        if user.email != claims.get("email", "") and claims.get("email"):
            user.email = claims["email"]
            user.save(update_fields=["email"])
        return user, claims
