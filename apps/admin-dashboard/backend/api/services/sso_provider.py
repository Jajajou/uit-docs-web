"""Provider-ready SSO config and mapping helpers for the /web backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast
from urllib.parse import urlencode

import requests

from api.config import settings
from api.errors import ApiServiceError
from api.schemas import Role

SsoProviderMode = Literal["emulator", "external"]

VALID_ROLES: tuple[Role, ...] = ("guest", "student", "teacher", "admin")
INTERNAL_ROLE_PRIORITY: dict[Role, int] = {
    "teacher": 0,
    "admin": 1,
    "guest": -1,
    "student": -1,
}


def _normalize_mode(value: str) -> SsoProviderMode:
    return "external" if value.strip().lower() == "external" else "emulator"


def _parse_role_mapping(value: str) -> dict[str, Role]:
    mapping: dict[str, Role] = {}

    for raw_entry in value.split(","):
        if ":" not in raw_entry:
            continue
        raw_key, raw_role = raw_entry.split(":", 1)
        key = raw_key.strip().lower()
        role = raw_role.strip().lower()
        if key and role in VALID_ROLES:
            mapping[key] = cast(Role, role)

    return mapping


def _dedupe_groups(groups: list[str] | None) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for group in groups or []:
        normalized = group.strip()
        if not normalized:
            continue
        lower = normalized.lower()
        if lower in seen:
            continue
        seen.add(lower)
        result.append(normalized)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class SsoProviderConfig:
    mode: SsoProviderMode
    provider_name: str
    authorize_url: str | None
    token_url: str | None
    userinfo_url: str | None
    client_id: str | None
    client_secret: str | None
    scope: str
    hosted_domain: str | None
    callback_base_url: str | None
    callback_path: str
    role_claim: str
    group_claim: str
    email_claim: str
    group_role_map: dict[str, Role]
    role_hint_map: dict[str, Role]

    @property
    def uses_local_emulator(self) -> bool:
        return self.mode == "emulator"

    @property
    def configured(self) -> bool:
        if self.mode == "emulator":
            return True
        return bool(self.authorize_url and self.token_url and self.userinfo_url and self.client_id and self.client_secret)

    def build_callback_url(self, request_base_url: str) -> str:
        base_url = (self.callback_base_url or request_base_url).rstrip("/")
        return f"{base_url}{self.callback_path}"

    def build_start_redirect(self, *, state: str, request_base_url: str) -> str:
        if self.uses_local_emulator:
            return f"/api/auth/sso/provider?{urlencode({'state': state})}"

        authorize_url = self.authorize_url or ""
        query_params = {
            "response_type": "code",
            "client_id": self.client_id or "",
            "redirect_uri": self.build_callback_url(request_base_url),
            "scope": self.scope,
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        }
        if self.hosted_domain:
            query_params["hd"] = self.hosted_domain
        query = urlencode(query_params)
        return f"{authorize_url}?{query}"

    def resolve_role(self, *, role_hint: str | None = None, groups: list[str] | None = None) -> Role | None:
        candidates: list[Role] = []
        normalized_hint = (role_hint or "").strip().lower()
        if normalized_hint in self.role_hint_map:
            candidates.append(self.role_hint_map[normalized_hint])
        elif normalized_hint in VALID_ROLES:
            candidates.append(cast(Role, normalized_hint))

        for group in _dedupe_groups(groups):
            mapped_role = self.group_role_map.get(group.lower())
            if mapped_role:
                candidates.append(mapped_role)

        if not candidates:
            return None

        return max(candidates, key=lambda role: INTERNAL_ROLE_PRIORITY.get(role, -1))

    def exchange_code_for_identity(self, *, code: str, request_base_url: str) -> "SsoProviderIdentity":
        if self.uses_local_emulator:
            raise ApiServiceError(
                status_code=400,
                code="sso_provider_not_external",
                message="The active provider is running in emulator mode and cannot exchange an authorization code.",
            )

        if not self.configured:
            raise ApiServiceError(
                status_code=503,
                code="sso_provider_not_configured",
                message="Google OAuth is not configured for the /web backend.",
            )

        token_payload = {
            "code": code,
            "client_id": self.client_id or "",
            "client_secret": self.client_secret or "",
            "redirect_uri": self.build_callback_url(request_base_url),
            "grant_type": "authorization_code",
        }

        try:
            token_response = requests.post(self.token_url or "", data=token_payload, timeout=15)
            token_response.raise_for_status()
        except requests.RequestException as exc:
            raise ApiServiceError(
                status_code=502,
                code="sso_token_exchange_failed",
                message="Google OAuth token exchange failed.",
                details=str(exc),
            ) from exc

        token_body = token_response.json()
        access_token = str(token_body.get("access_token") or "").strip()
        if not access_token:
            raise ApiServiceError(
                status_code=502,
                code="sso_access_token_missing",
                message="Google OAuth did not return an access token.",
            )

        try:
            profile_response = requests.get(
                self.userinfo_url or "",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15,
            )
            profile_response.raise_for_status()
        except requests.RequestException as exc:
            raise ApiServiceError(
                status_code=502,
                code="sso_userinfo_failed",
                message="Google OAuth user profile lookup failed.",
                details=str(exc),
            ) from exc

        profile = profile_response.json()
        email = str(profile.get(self.email_claim) or "").strip().lower()
        if not email:
            raise ApiServiceError(
                status_code=502,
                code="sso_email_missing",
                message="Google OAuth profile did not include an email address.",
            )

        name = str(profile.get("name") or profile.get("given_name") or email.split("@", 1)[0]).strip()
        hosted_domain = str(profile.get("hd") or "").strip().lower() or None

        return SsoProviderIdentity(email=email, name=name, hosted_domain=hosted_domain)


@dataclass(frozen=True, slots=True)
class SsoProviderIdentity:
    email: str
    name: str
    hosted_domain: str | None = None


@dataclass(frozen=True, slots=True)
class SsoProviderMetadata:
    mode: SsoProviderMode
    provider_name: str
    uses_local_emulator: bool
    configured: bool
    authorization_endpoint: str | None
    callback_path: str
    role_claim: str
    group_claim: str
    email_claim: str
    default_scope: str


def get_sso_provider_config() -> SsoProviderConfig:
    return SsoProviderConfig(
        mode=_normalize_mode(settings.SSO_PROVIDER_MODE),
        provider_name=settings.SSO_PROVIDER_NAME.strip() or "Google Workspace UIT",
        authorize_url=settings.SSO_AUTHORIZE_URL.strip() or None,
        token_url=settings.SSO_TOKEN_URL.strip() or None,
        userinfo_url=settings.SSO_USERINFO_URL.strip() or None,
        client_id=settings.SSO_CLIENT_ID.strip() or None,
        client_secret=settings.SSO_CLIENT_SECRET.strip() or None,
        scope=settings.SSO_SCOPE.strip() or "openid email profile",
        hosted_domain=settings.SSO_HOSTED_DOMAIN.strip().lower() or None,
        callback_base_url=settings.SSO_CALLBACK_BASE_URL.strip() or None,
        callback_path="/api/auth/sso/callback",
        role_claim=settings.SSO_ROLE_CLAIM.strip() or "role",
        group_claim=settings.SSO_GROUP_CLAIM.strip() or "groups",
        email_claim=settings.SSO_EMAIL_CLAIM.strip() or "email",
        group_role_map=_parse_role_mapping(settings.SSO_GROUP_ROLE_MAP),
        role_hint_map=_parse_role_mapping(settings.SSO_ROLE_HINT_MAP),
    )


def build_sso_provider_metadata() -> SsoProviderMetadata:
    config = get_sso_provider_config()
    return SsoProviderMetadata(
        mode=config.mode,
        provider_name=config.provider_name,
        uses_local_emulator=config.uses_local_emulator,
        configured=config.configured,
        authorization_endpoint=None if config.uses_local_emulator else config.authorize_url,
        callback_path=config.callback_path,
        role_claim=config.role_claim,
        group_claim=config.group_claim,
        email_claim=config.email_claim,
        default_scope=config.scope,
    )
