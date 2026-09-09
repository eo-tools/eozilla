#  Copyright (c) 2025-2026 by the Eozilla team and contributors
#  Permissions are hereby granted under the terms of the Apache 2.0 License:
#  https://opensource.org/license/apache-2.0.

from cuiman.api.auth.config import (
    ApiKeyAuthConfig,
    AuthConfig,
    AuthConfigBase,
    AuthType,
    BasicAuthConfig,
    LoginAuthConfig,
    NoAuthConfig,
    OAuth2AuthConfig,
    OAuth2GrantType,
    OidcAuthConfig,
    SecretFields,
    TokenAuthConfig,
)
from cuiman.api.auth.login import login
from cuiman.api.auth.login_async import login_async
from cuiman.api.auth.oauth2 import obtain_oauth2_tokens, renew_oauth2_tokens
from cuiman.api.auth.oauth2_async import (
    obtain_oauth2_tokens_async,
    renew_oauth2_tokens_async,
)
from cuiman.api.auth.oidc import (
    LoopbackCallbackServer,
    OidcDiscovery,
    build_authorization_url,
    discover_oidc_provider,
    exchange_oidc_code,
    generate_pkce_verifier,
    renew_oidc_tokens,
    revoke_oidc_tokens,
)
from cuiman.api.auth.oidc_async import renew_oidc_tokens_async
from cuiman.api.auth.session import LoginRequiredError
from cuiman.api.auth.tokens import TokenResult

__all__ = [
    "LoginRequiredError",
    "ApiKeyAuthConfig",
    "AuthConfig",
    "AuthConfigBase",
    "AuthType",
    "BasicAuthConfig",
    "LoginAuthConfig",
    "NoAuthConfig",
    "OidcAuthConfig",
    "OAuth2AuthConfig",
    "OAuth2GrantType",
    "SecretFields",
    "TokenAuthConfig",
    "TokenResult",
    "login",
    "login_async",
    "obtain_oauth2_tokens",
    "obtain_oauth2_tokens_async",
    "renew_oauth2_tokens",
    "renew_oauth2_tokens_async",
    "LoopbackCallbackServer",
    "OidcDiscovery",
    "build_authorization_url",
    "discover_oidc_provider",
    "exchange_oidc_code",
    "generate_pkce_verifier",
    "renew_oidc_tokens",
    "revoke_oidc_tokens",
    "renew_oidc_tokens_async",
]
