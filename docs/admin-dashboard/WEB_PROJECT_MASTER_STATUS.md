# WEB PROJECT MASTER STATUS

## 1. Scope

This file is the single source of truth for the current state of the `/web` workspace.

In scope:

- `web/apps/admin-dashboard/frontend`
- `web/apps/admin-dashboard/backend`
- `web/docs/admin-dashboard`

Out of scope:

- any service or code outside `/web`

Reference date:

- `2026-03-24`

## 2. Workspace structure

```text
web/
  apps/
    admin-dashboard/
      backend/
      frontend/
  docs/
    admin-dashboard/
      WEB_PROJECT_MASTER_STATUS.md
  design/
    admin-dashboard/
      uxui_screen/
```

## 3. Final architecture inside `/web`

### 3.1 Frontend

- one React app
- three shells:
  - `Public`
  - `Portal`
  - `Admin`
- role-driven route guards based on `Session.user.role`
- shared DTO mappers, query hooks, and design-system primitives
- lazy routes, manual chunking, route prefetch
- axios mock adapter as the only active browser-side mock strategy

### 3.2 Backend

- FastAPI BFF aligned to the frontend contract
- in-memory workspace service for local tests and live `/web` regression
- normalized error envelope
- cookie-backed auth session via `uit_web_session`
- provider-ready SSO layer behind backend auth routers

## 4. What has been completed

### 4.1 Frontend foundation

- workspace structure normalized
- app structure normalized to:
  - `app`
  - `entities`
  - `features`
  - `layouts`
  - `pages`
  - `shared`
  - `mocks`
- design system foundation and Storybook
- route guards, `403`, `404`, loading and error states
- lazy loading and chunk splitting

### 4.2 Public features

- home page
- chat page
- citation navigation to document detail
- confidence and warning states
- archived-citation handling

### 4.3 Lecturer and operator flows

- upload by file, text, and URL
- upload validation and duplicate-upload handling
- submissions list and submission detail
- review queue
- review decisions
- library filters
- jobs monitor and retry
- document detail
- archive and reindex actions

### 4.4 Admin features

- users
- roles matrix
- settings
- audit logs
- explicit admin break-glass wording for operator-owned remediation flows

### 4.5 Document lifecycle

- version history
- related activity history
- audit deep links
- v2 traceability:
  - submission -> review -> published document linkage
  - version-level metadata diff highlights
  - read-only traceability surfaces

### 4.6 Auth and SSO

- local/mock auth bootstrap through `/api/auth/bootstrap`
- cookie-backed session resolution through `/api/auth/me`
- backend-owned SSO kickoff:
  - `GET /api/auth/sso/metadata`
  - `GET /api/auth/sso/start`
  - `GET /api/auth/sso/callback`
  - `POST /api/auth/logout`
- current live mode still uses a local `/web` provider emulator by default
- backend is now provider-ready for a real institutional SSO handoff

## 5. Current frontend routes

### 5.1 Public

- `/`
- `/chat`
- `/documents/:id`

### 5.2 Auth

- `/auth/login`
- `/auth/callback`

### 5.3 Portal

- `/portal`
- `/portal/upload`
- `/portal/submissions`
- `/portal/submissions/:id`
- `/portal/review`
- `/portal/library`
- `/portal/jobs`

### 5.4 Admin

- `/admin/users`
- `/admin/roles`
- `/admin/settings`
- `/admin/audit-logs`

## 6. Current backend contract

### 6.1 Auth

- `POST /api/auth/bootstrap`
- `GET /api/auth/me`
- `GET /api/auth/sso/metadata`
- `GET /api/auth/sso/start`
- `GET /api/auth/sso/callback`
- `POST /api/auth/logout`

### 6.2 App endpoints

- `GET /api/chat/sessions`
- `POST /api/chat/stream`
- `POST /api/uploads/file`
- `POST /api/uploads/text`
- `POST /api/uploads/url`
- `POST /api/uploads/scan`
- `GET /api/submissions`
- `GET /api/submissions/{id}`
- `GET /api/reviews`
- `POST /api/reviews/{id}/decision`
- `GET /api/jobs`
- `POST /api/jobs/{id}/retry`
- `GET /api/documents`
- `GET /api/documents/{id}`
- `POST /api/documents/{id}/archive`
- `POST /api/documents/{id}/reindex`
- `GET /api/admin/users`
- `PATCH /api/admin/users/{id}`
- `GET /api/admin/roles`
- `GET /api/admin/settings`
- `PATCH /api/admin/settings/{key}`
- `GET /api/admin/audit-logs`

## 7. Quality status

### 7.1 Frontend

Latest verified status:

- `npm run typecheck`: PASS
- `npm run lint`: PASS
- `npm run test`: PASS, `44` tests
- `npm run test:e2e`: PASS, `12` tests
- `npm run test:e2e:live`: PASS, `7` tests
- `npm run build`: PASS
- `npm run build-storybook`: PASS on the last shared-UI pass

### 7.2 Backend

Latest verified status:

- `python -m ruff check .`: PASS
- `python -m pytest`: PASS, `41` tests

## 8. Clean decisions already locked

- frontend contract is the source of truth inside `/web`
- internal email policy is `@gm.uit.edu.vn`
- operator owns operational mutations
- admin is governance + narrow audited break-glass override
- browser mock strategy is axios-adapter-only
- document lifecycle v2 is read-first only
- restore and rollback actions are deferred

## 9. What still remains

Only one major item remains:

- replace the local `/web` SSO emulator with the real institutional provider

This is no longer an architecture task inside `/web`.
It is now an integration activation task that depends on external inputs.

## 10. External inputs required for the real SSO switch

Needed from outside `/web`:

1. `SSO_AUTHORIZE_URL`
2. `SSO_CLIENT_ID`
3. callback registration for `/api/auth/sso/callback`
4. claim mapping for:
   - email
   - direct role hint if any
   - groups / entitlements

## 11. Files already prepared for the real SSO switch

- config template:
  - `web/apps/admin-dashboard/backend/.env.sso.example`
- backend provider abstraction:
  - `web/apps/admin-dashboard/backend/api/services/sso_provider.py`
- backend auth router:
  - `web/apps/admin-dashboard/backend/api/routers/auth.py`

## 12. Next steps

### 12.1 Immediate next step

Provide the real SSO values:

- authorize URL
- client id
- callback registration confirmation
- group / claim mapping

### 12.2 After those values are available

1. fill backend `.env`
2. switch `SSO_PROVIDER_MODE=external`
3. restart backend
4. confirm `/auth/login` no longer reports local emulator mode
5. rerun:
   - `npm run test:e2e:live`
6. manually verify:
   - lecturer login
   - operator login
   - admin login
   - non-compliant email denial
   - logout

## 13. Acceptance condition for final `/web` completion

`/web` is fully complete when:

1. the real institutional provider replaces the local emulator
2. `/api/auth/sso/start` redirects to the real provider
3. `/api/auth/sso/callback` completes with the real provider
4. `uit_web_session` is still issued correctly
5. protected routes still resolve correctly by role
6. live regression still passes
