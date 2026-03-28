"""Provider-ready SSO config and mapping helpers for the /web backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast
from urllib.parse import urlencode

from api.config import settings
from api.schemas import Role

SsoProviderMode = Literal["emulator", "external"]

VALID_ROLES: tuple[Role, ...] = ("guest", "student", "lecturer", "operator", "admin")
INTERNAL_ROLE_PRIORITY: dict[Role, int] = {
    "lecturer": 0,
    "operator": 1,
    "admin": 2,
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
    client_id: str | None
    scope: str
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
        return bool(self.authorize_url and self.client_id)

    def build_callback_url(self, request_base_url: str) -> str:
        base_url = (self.callback_base_url or request_base_url).rstrip("/")
        return f"{base_url}{self.callback_path}"

    def build_start_redirect(self, *, state: str, request_base_url: str) -> str:
        if self.uses_local_emulator:
            return f"/api/auth/sso/provider?{urlencode({'state': state})}"

        authorize_url = self.authorize_url or ""
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.client_id or "",
                "redirect_uri": self.build_callback_url(request_base_url),
                "scope": self.scope,
                "state": state,
            }
        )
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
        provider_name=settings.SSO_PROVIDER_NAME.strip() or "UIT Institutional SSO",
        authorize_url=settings.SSO_AUTHORIZE_URL.strip() or None,
        client_id=settings.SSO_CLIENT_ID.strip() or None,
        scope=settings.SSO_SCOPE.strip() or "openid profile email groups",
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
        authorization_endpoint=config.authorize_url,
        callback_path=config.callback_path,
        role_claim=config.role_claim,
        group_claim=config.group_claim,
        email_claim=config.email_claim,
        default_scope=config.scope,
    )
