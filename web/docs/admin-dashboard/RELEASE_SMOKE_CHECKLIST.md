# Release Smoke Checklist

Last updated: 2026-04-12

This checklist is for pre-release validation of the `/web` admin dashboard in staging or production-like environments.

## 1. Environment

- Frontend is reachable on the target domain.
- Backend health endpoint returns `200`.
- Production secrets are injected from environment or secret manager.
- `TEST_MODE` is disabled.
- `ENABLE_DEMO_AUTH` is disabled.
- `TRUSTED_HOSTS` contains only the intended backend hostnames.
- `FORCE_HTTPS_REDIRECT` is enabled for production HTTPS environments.
- Session cookies are `Secure`, `HttpOnly`, `SameSite=Lax`, and use the intended cookie domain.

## 2. Google OAuth

- Google OAuth credential uses the correct redirect URI for the target environment.
- Hosted domain restriction is configured for `gm.uit.edu.vn`.
- Sign-in with a valid `@gm.uit.edu.vn` account succeeds.
- Sign-in with a non-`@gm.uit.edu.vn` account is rejected with a clear message.
- Callback returns to the frontend domain, not the backend origin.
- Logout clears the session and blocks access to protected routes.

## 3. Role and Access Control

- New Google user lands as `student` by default.
- `student` can access chat and cannot access upload or manager routes.
- `teacher` can access chat and upload, but cannot access manager routes.
- `admin` can access chat, upload and manager routes.
- Admin role changes take effect on the next session validation cycle.

## 4. Public Surface Security

- Public chat citations do not expose internal-only provenance fields.
- Public document detail does not expose `owner_email`, raw `file_source`, `content_hash` or internal workflow IDs.
- Internal-only documents do not appear in the student/public catalog.
- Error responses do not leak stack traces.
- Requests with an unexpected `Host` header are rejected.
- HTTP requests are redirected to HTTPS in the production environment.

## 5. Upload and Review Workflow

- Teacher upload by text works end to end.
- Teacher upload by file or URL returns the expected submission state.
- Review queue loads and an admin can approve or reject a submission.
- Approved submission appears in the document library with the expected visibility.
- Reindex and archive actions update UI state and backend responses consistently.

## 6. UI Regression

- Light mode chat, upload and manager pages render correctly.
- Dark mode chat, upload and manager pages render correctly.
- Mobile chat and manager filters remain usable on narrow screens.
- WebKit mobile smoke passes if the release target includes Safari users.

## 7. Observability

- `x-request-id` is present in backend responses.
- Failed auth or API calls can be traced in server logs.
- CI artifacts for coverage, Playwright and pytest are available for the release candidate build.
- Secret rotation has been completed for any credential previously exposed in local chat, logs or screenshots.
