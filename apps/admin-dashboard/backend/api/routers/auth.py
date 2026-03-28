"""Auth routes aligned with the frontend session contract."""

from __future__ import annotations

from html import escape
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from api.dependencies import (
    INTERNAL_ROLES,
    SESSION_COOKIE_NAME,
    ApiContext,
    ensure_internal_session_compliance,
    get_api_context,
    get_workspace_service,
)
from api.errors import ApiServiceError
from api.schemas import AuthBootstrapRequest, SessionDto, SsoProviderMetadataDto
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
    params: dict[str, str] = {}
    safe_return_to = normalize_return_to(return_to)

    if safe_return_to:
        params["returnTo"] = safe_return_to
    if auth_error:
        params["authError"] = auth_error
    if auth_error_message:
        params["authErrorMessage"] = auth_error_message

    if not params:
        return "/auth/callback"

    return f"/auth/callback?{urlencode(params)}"


def render_sso_provider_emulator(*, state: str, return_to: str | None, provider_name: str) -> str:
    safe_return_to = normalize_return_to(return_to) or "/"
    role_links = [
        ("Lecturer", f"/api/auth/sso/callback?{urlencode({'state': state, 'providerRole': 'lecturer'})}"),
        ("Operator", f"/api/auth/sso/callback?{urlencode({'state': state, 'providerRole': 'operator'})}"),
        ("Admin", f"/api/auth/sso/callback?{urlencode({'state': state, 'providerRole': 'admin'})}"),
    ]
    edge_links = [
        (
            "Simulate non-compliant internal email",
            f"/api/auth/sso/callback?{urlencode({'state': state, 'providerRole': 'lecturer', 'scenario': 'non-compliant-internal-email'})}",
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
    session = service.get_session(payload.role, scenario)
    ensure_internal_session_compliance(payload.role, session)
    session_token = service.issue_session_token(payload.role)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return session


@router.get("/sso/start")
async def start_sso(
    request: Request,
    return_to: Annotated[str | None, Query(alias="returnTo")] = None,
    scenario: Annotated[str, Query()] = "happy",
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> RedirectResponse:
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

    if not provider_config.uses_local_emulator and not code and not provider_role and not provider_groups:
        return RedirectResponse(
            url=build_frontend_callback_url(
                return_to=return_to,
                auth_error="missing_sso_code",
                auth_error_message="The institutional provider callback did not include an authorization code.",
            ),
            status_code=302,
        )

    role = provider_config.resolve_role(role_hint=provider_role, groups=provider_groups)
    if role not in INTERNAL_ROLES:
        return RedirectResponse(
            url=build_frontend_callback_url(
                return_to=return_to,
                auth_error="unauthorized_internal_role",
                auth_error_message="The authenticated account does not map to an allowed internal role.",
            ),
            status_code=302,
        )

    try:
        session = service.get_session(role, scenario_key)
        if provider_email:
            session["user"]["email"] = provider_email
        if provider_name:
            session["user"]["name"] = provider_name
        ensure_internal_session_compliance(role, session)
    except ApiServiceError as exc:
        return RedirectResponse(
            url=build_frontend_callback_url(
                return_to=return_to,
                auth_error=exc.code,
                auth_error_message=exc.message,
            ),
            status_code=302,
        )

    session_token = service.issue_session_token(role, auth_method="institutional_sso")
    redirect = RedirectResponse(url=build_frontend_callback_url(return_to=return_to), status_code=302)
    redirect.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return redirect


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> Response:
    service.revoke_session_token(request.cookies.get(SESSION_COOKIE_NAME))
    response = Response(status_code=204)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return response


@router.get("/me", response_model=SessionDto)
async def get_me(
    context: ApiContext = Depends(get_api_context),
    service: InMemoryWorkspaceService = Depends(get_workspace_service),
) -> dict:
    return service.get_session(context.role, context.scenario)
