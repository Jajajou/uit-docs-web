"""Auth routes aligned with the frontend session contract."""

from __future__ import annotations

from html import escape
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from api.config import settings
from api.dependencies import (
    INTERNAL_EMAIL_DOMAIN,
    INTERNAL_ROLES,
    SESSION_COOKIE_NAME,
    ApiContext,
    ensure_internal_session_compliance,
    get_api_context,
    get_workspace_service,
)
from api.errors import ApiServiceError
from api.schemas import AuthBootstrapRequest, SessionDto, SsoProviderMetadataDto
from api.security import build_session_cookie_settings, enforce_auth_rate_limit
from api.services.sso_provider import build_sso_provider_metadata, get_sso_provider_config
from api.services.workspace_service import InMemoryWorkspaceService

router = APIRouter()


def normalize_return_to(return_to: str | None) -> str | None:
    if return_to and return_to.startswith("/") and not return_to.startswith("//"):
        return return_to
    return None


def build_frontend_callback_url(
    *,
    return_to: str | None = None,
    auth_error: str | None = None,
    auth_error_message: str | None = None,
) -> str:
    frontend_base_url = settings.SSO_FRONTEND_BASE_URL.rstrip("/")
    params: dict[str, str] = {}
    safe_return_to = normalize_return_to(return_to)

    if safe_return_to:
        params["returnTo"] = safe_return_to
    if auth_error:
        params["authError"] = auth_error
    if auth_error_message:
        params["authErrorMessage"] = auth_error_message

    if not params:
        return f"{frontend_base_url}/auth/callback"

    return f"{frontend_base_url}/auth/callback?{urlencode(params)}"


def render_sso_provider_emulator(*, state: str, return_to: str | None, provider_name: str) -> str:
    safe_return_to = normalize_return_to(return_to) or "/"
    role_links = [
        ("Teacher", f"/api/auth/sso/callback?{urlencode({'state': state, 'providerRole': 'teacher'})}"),
        ("Admin", f"/api/auth/sso/callback?{urlencode({'state': state, 'providerRole': 'admin'})}"),
    ]
    edge_links = [
        (
            "Simulate non-compliant internal email",
            f"/api/auth/sso/callback?{urlencode({'state': state, 'providerRole': 'teacher', 'scenario': 'non-compliant-internal-email'})}",
        ),
        (
            "Simulate provider access denied",
            f"/api/auth/sso/callback?{urlencode({'state': state, 'error': 'access_denied', 'error_description': 'The institutional provider denied access.'})}",
        ),
    ]

    role_buttons = "".join(
        (
            f'<a href="{escape(link)}" '
            'style="display:block;padding:14px 16px;border-radius:14px;border:1px solid #d1d5db;'
            'text-decoration:none;color:#111827;background:#ffffff;font-weight:600;">'
            f"Continue as {escape(label)}</a>"
        )
        for label, link in role_links
    )
    edge_cases = "".join(
        f'<li><a href="{escape(link)}" style="color:#92400e;text-decoration:none;">{escape(label)}</a></li>'
        for label, link in edge_links
    )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(provider_name)} Emulator</title>
  </head>
  <body style="margin:0;background:#f8fafc;color:#0f172a;font-family:Segoe UI,Arial,sans-serif;">
    <main style="max-width:720px;margin:48px auto;padding:24px;">
      <section style="background:#ffffff;border:1px solid #e2e8f0;border-radius:24px;padding:24px 24px 28px;box-shadow:0 10px 30px rgba(15,23,42,0.08);">
        <div style="display:inline-block;padding:6px 10px;border-radius:999px;background:#dbeafe;color:#1d4ed8;font-size:12px;font-weight:700;">
          Local /web provider emulator
        </div>
        <h1 style="margin:16px 0 8px;font-size:28px;line-height:1.2;">{escape(provider_name)}</h1>
        <p style="margin:0 0 18px;color:#475569;line-height:1.6;">
          This page stands in for the external identity provider during the `/web` SSO kickoff. Choose an internal profile to continue.
        </p>
        <p style="margin:0 0 24px;font-size:14px;color:#64748b;">
          Requested return path: <strong>{escape(safe_return_to)}</strong>
        </p>
        <div style="display:grid;gap:12px;">{role_buttons}</div>
        <section style="margin-top:24px;padding-top:20px;border-top:1px solid #e2e8f0;">
          <div style="font-size:14px;font-weight:700;color:#92400e;">Negative path shortcuts</div>
          <ul style="margin:12px 0 0;padding-left:18px;display:grid;gap:8px;color:#92400e;">
            {edge_cases}
          </ul>
        </section>
      </section>
    </main>
  </body>
</html>"""


@router.get("/sso/metadata", response_model=SsoProviderMetadataDto)
async def get_sso_metadata() -> dict:
    metadata = build_sso_provider_metadata()
    return {
        "mode": metadata.mode,
        "provider_name": metadata.provider_name,
        "uses_local_emulator": metadata.uses_local_emulator,
        "configured": metadata.configured,
        "authorization_endpoint": metadata.authorization_endpoint,
        "callback_path": metadata.callback_path,
        "role_claim": metadata.role_claim,
        "group_claim": metadata.group_claim,
        "email_claim": metadata.email_claim,
        "default_scope": metadata.default_scope,
    }


@router.post("/bootstrap", response_model=SessionDto)
async def bootstrap_session(
    payload: AuthBootstrapRequest,
    response: Response,
    scenario: Annotated[str, Query()] = "happy",
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    if not settings.ENABLE_DEMO_AUTH:
        raise ApiServiceError(
            status_code=404,
            code="demo_auth_disabled",
            message="Demo bootstrap is disabled in the current environment.",
        )
    session = service.get_session(payload.role, scenario)
    ensure_internal_session_compliance(payload.role, session)
    session_token = service.issue_session_token(payload.role, session=session)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        **build_session_cookie_settings(),
    )
    return session


@router.get("/sso/start")
async def start_sso(
    request: Request,
    return_to: Annotated[str | None, Query(alias="returnTo")] = None,
    scenario: Annotated[str, Query()] = "happy",
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> RedirectResponse:
    enforce_auth_rate_limit(request, bucket="auth-sso-start")
    sso_state = service.issue_sso_state(normalize_return_to(return_to), scenario)
    provider_config = get_sso_provider_config()
    if not provider_config.configured:
        return RedirectResponse(
            url=build_frontend_callback_url(
                return_to=return_to,
                auth_error="sso_provider_not_configured",
                auth_error_message="The institutional SSO provider is not configured for /web yet.",
            ),
            status_code=302,
        )
    return RedirectResponse(
        url=provider_config.build_start_redirect(state=sso_state, request_base_url=str(request.base_url)),
        status_code=302,
    )


@router.get("/sso/provider", response_class=HTMLResponse)
async def sso_provider(
    state: Annotated[str, Query()],
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> HTMLResponse:
    provider_config = get_sso_provider_config()
    if not provider_config.uses_local_emulator:
        return HTMLResponse(
            "<h1>Provider emulator disabled</h1><p>The active SSO configuration uses an external provider redirect.</p>",
            status_code=404,
        )
    stored_state = service.read_sso_state(state)
    if stored_state is None:
        return HTMLResponse("<h1>Invalid SSO state</h1><p>The sign-in flow has expired or is invalid.</p>", status_code=400)

    return HTMLResponse(
        render_sso_provider_emulator(
            state=state,
            return_to=stored_state.get("return_to"),
            provider_name=provider_config.provider_name,
        )
    )


@router.get("/sso/callback")
async def sso_callback(
    request: Request,
    state: Annotated[str, Query()],
    provider_role: Annotated[str | None, Query(alias="providerRole")] = None,
    provider_groups: Annotated[list[str] | None, Query(alias="providerGroup")] = None,
    provider_email: Annotated[str | None, Query(alias="providerEmail")] = None,
    provider_name: Annotated[str | None, Query(alias="providerName")] = None,
    code: Annotated[str | None, Query()] = None,
    scenario: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query(alias="error_description")] = None,
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> RedirectResponse:
    enforce_auth_rate_limit(request, bucket="auth-sso-callback")
    provider_config = get_sso_provider_config()
    stored_state = service.consume_sso_state(state)
    if stored_state is None:
        return RedirectResponse(
            url=build_frontend_callback_url(
                auth_error="invalid_sso_state",
                auth_error_message="The institutional sign-in state is missing or has expired.",
            ),
            status_code=302,
        )

    return_to = stored_state.get("return_to")
    scenario_key = scenario or stored_state.get("scenario") or "happy"

    if error:
        return RedirectResponse(
            url=build_frontend_callback_url(
                return_to=return_to,
                auth_error=error,
                auth_error_message=error_description or "Institutional sign-in did not complete successfully.",
            ),
            status_code=302,
        )

    try:
        if provider_config.uses_local_emulator:
            role = provider_config.resolve_role(role_hint=provider_role, groups=provider_groups)
            if role not in INTERNAL_ROLES:
                raise ApiServiceError(
                    status_code=403,
                    code="unauthorized_internal_role",
                    message="The authenticated account does not map to an allowed internal role.",
                )

            session = service.get_session(role, scenario_key)
            if provider_email:
                session["user"]["email"] = provider_email
            if provider_name:
                session["user"]["name"] = provider_name
            ensure_internal_session_compliance(role, session)
            auth_method = "institutional_sso_emulator"
        else:
            if not code:
                raise ApiServiceError(
                    status_code=400,
                    code="missing_sso_code",
                    message="The Google OAuth callback did not include an authorization code.",
                )

            identity = provider_config.exchange_code_for_identity(code=code, request_base_url=str(request.base_url))
            if not identity.email.endswith(INTERNAL_EMAIL_DOMAIN):
                raise ApiServiceError(
                    status_code=403,
                    code="unsupported_google_domain",
                    message=f"Only Google accounts ending with {INTERNAL_EMAIL_DOMAIN} are supported.",
                )

            role, session = service.build_google_sso_session(identity.email, identity.name)
            ensure_internal_session_compliance(role, session)
            auth_method = "google_oauth"
    except ApiServiceError as exc:
        return RedirectResponse(
            url=build_frontend_callback_url(
                return_to=return_to,
                auth_error=exc.code,
                auth_error_message=exc.message,
            ),
            status_code=302,
        )

    session_token = service.issue_session_token(role, auth_method=auth_method, session=session)
    redirect = RedirectResponse(url=build_frontend_callback_url(return_to=return_to), status_code=302)
    redirect.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        **build_session_cookie_settings(),
    )
    return redirect


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> Response:
    service.revoke_session_token(request.cookies.get(SESSION_COOKIE_NAME))
    response = Response(status_code=204)
    response.delete_cookie(key=SESSION_COOKIE_NAME, **build_session_cookie_settings())
    return response


@router.get("/me", response_model=SessionDto)
async def get_me(
    context: ApiContext = Depends(get_api_context),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return context.session or service.get_session(context.role, context.scenario)
