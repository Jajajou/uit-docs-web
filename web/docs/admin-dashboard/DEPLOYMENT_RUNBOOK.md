# Deployment Runbook

Last updated: 2026-04-12

This runbook covers the recommended production split for the `/web` admin dashboard.

## Topology

- Frontend: Vercel deploy from `web/apps/admin-dashboard/frontend`
- Backend: VM or container host running `web/apps/admin-dashboard/backend`
- Domains:
  - `app.gm.uit.edu.vn`
  - `api.gm.uit.edu.vn`

## Frontend deployment

- Build command: `npm run build`
- Output directory: `dist`
- Runtime: static SPA
- Required frontend env:
  - `VITE_ENABLE_MOCKS=false`
  - `VITE_API_BASE_URL=https://api.gm.uit.edu.vn`

## Backend deployment

- Container entrypoint: `uvicorn api.main:app --host 0.0.0.0 --port 8001`
- Required backend env:
  - `CORS_ORIGINS=https://app.gm.uit.edu.vn`
  - `TRUSTED_HOSTS=api.gm.uit.edu.vn`
  - `FORCE_HTTPS_REDIRECT=true`
  - `SESSION_COOKIE_SECURE=true`
  - `SESSION_COOKIE_SAMESITE=lax`
  - `SESSION_COOKIE_DOMAIN=.gm.uit.edu.vn`
  - `SSO_PROVIDER_MODE=external`
  - `SSO_CALLBACK_BASE_URL=https://api.gm.uit.edu.vn`
  - `SSO_FRONTEND_BASE_URL=https://app.gm.uit.edu.vn`
  - `ENABLE_DEMO_AUTH=false`
  - `TEST_MODE=false`
  - `EXPOSE_ERROR_DETAILS=false`

## OAuth and domain restrictions

- Google OAuth redirect URI:
  - `https://api.gm.uit.edu.vn/api/auth/sso/callback`
- Hosted domain restriction:
  - `gm.uit.edu.vn`
- Backend must reject non-`@gm.uit.edu.vn` emails even if the Google hint is bypassed.

## Reverse proxy expectations

- Forward `x-forwarded-proto=https`
- Preserve the request host
- Terminate TLS before forwarding to the backend service

## Post-deploy smoke

- Run the checklist in `web/docs/admin-dashboard/RELEASE_SMOKE_CHECKLIST.md`
- Confirm:
  - login works for a valid UIT account
  - non-UIT account is rejected
  - chat works for student
  - upload works for teacher
  - manager works for admin
  - unknown `Host` is rejected
  - HTTP redirects to HTTPS

## Secret hygiene

- Never commit `.env`
- Inject production secrets through the platform secret store
- Rotate any OAuth client secret that has appeared in logs, screenshots or chat history
