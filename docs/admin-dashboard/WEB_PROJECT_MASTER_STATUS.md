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

- `2026-04-13`

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

## 3. Current architecture inside `/web`

### 3.1 Frontend

- one React app
- three user experiences:
  - `student`
  - `teacher`
  - `admin`
- three shell layouts:
  - `app`
  - `auth`
  - `system`
- role-driven route guards based on `Session.user.role`
- shared DTO mappers, query hooks, and design-system primitives
- lazy routes, manual chunking, route prefetch
- axios mock adapter as the only active browser-side mock strategy
- portal overview backed by `/api/analytics/*` through a dedicated frontend analytics entity layer

### 3.2 Backend

- FastAPI BFF aligned to the frontend contract
- SqlAlchemy-backed normalized persistence (all 13 domains have dedicated tables, no blob state)
- business/service layer still mutates in-memory state then persists via `_persist_state()`; repository refactor pending
- normalized error envelope
- cookie-backed auth session via `uit_web_session`
- Google OAuth external SSO flow code-complete (token exchange, userinfo, domain restriction); env-dependent activation
- analytics endpoints available under `/api/analytics/*`

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
- UIT blue/white shell, light mode, dark mode, Google-only login UX

### 4.2 Student experience

- chat page
- citation navigation to document detail
- confidence and warning states
- archived-citation handling
- compact drawer-based chat UI for history and document sources

### 4.3 Teacher experience

- upload by file, text, and URL
- upload validation and duplicate-upload handling
- access to upload and document detail surfaces

### 4.4 Admin experience

- manager shell at `/manager`
- users
- roles matrix
- settings
- audit logs
- review queue
- review decisions
- jobs monitor and retry
- library filters
- archive and reindex actions

### 4.5 Analytics and document lifecycle

- portal overview wired to:
  - `/api/analytics/overview`
  - `/api/analytics/pipeline`
  - `/api/analytics/health`
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
- Google OAuth external flow is code-complete:
  - `sso_provider.py` has full `exchange_code_for_identity()` with token exchange and userinfo
  - `auth.py` callback handles both emulator and external mode
  - domain restriction to `@gm.uit.edu.vn` enforced
- activation requires env vars: `SSO_PROVIDER_MODE=external`, `SSO_CLIENT_ID`, `SSO_CLIENT_SECRET`
- default mode remains local emulator for development and testing

### 4.7 Persistence and test foundation

- all 13 workspace domains are normalized in SQLAlchemy tables
- bare `pytest` now works with `testpaths` + expanded `norecursedirs`
- frontend has coverage, Chromium e2e, WebKit mobile, live, a11y, and visual lanes in the toolchain

## 5. Current frontend routes

### 5.1 App/public

- `/`
- `/chat`
- `/documents/:id`

### 5.2 Auth

- `/auth/login`
- `/auth/callback`

### 5.3 Contributor

- `/knowledge`
- `/upload`

### 5.4 Admin

- `/manager`

### 5.5 System

- `/403`
- `*`

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
- `GET /api/analytics/overview`
- `GET /api/analytics/pipeline`
- `GET /api/analytics/graph-stats`
- `GET /api/analytics/health`

## 7. Quality status

### 7.1 Frontend

Latest verified status:

- `npm run typecheck`: PASS
- `npm run lint`: PASS
- `npm run test:coverage`: PASS, `88` tests
- `npm run test:e2e`: PASS, `15` tests
- `npm run test:e2e:webkit`: PASS, `2` tests
- `npm run build`: PASS
- `npm run build-storybook`: PASS on the last shared-UI pass
- `npm run check:ci`: currently stops at `test:e2e:live` if local port `8001` is already occupied by another process; this is a local harness conflict, not a confirmed app regression

### 7.2 Backend

Latest verified status:

- `python -m pytest --tb=short`: PASS, `65` tests

## 8. Clean decisions already locked

- frontend contract is the source of truth inside `/web`
- internal email policy is `@gm.uit.edu.vn`
- role model is `guest | student | teacher | admin`
- Google-only auth is the active UX contract
- browser mock strategy is axios-adapter-only
- analytics health UI must not expose raw `lightrag_url`
- document lifecycle v2 is read-first only
- restore and rollback actions are deferred

## 9. What still remains

Three categories of work remain:

### 9.1 Service-layer architecture

- refactor `workspace_service.py` to use repository methods instead of direct list/dict mutation + `_persist_state()`
- reduce dependence on full-snapshot persistence writes

### 9.2 Production persistence and integration

- migrate from SQLite to Postgres with Alembic migration scripts
- wire `/web` upload flow to real LightRAG / Firecrawl ingestion if live mode is needed

### 9.3 Activation and deploy hardening

- activate the Google OAuth external flow by providing env vars (`SSO_CLIENT_ID`, `SSO_CLIENT_SECRET`, `SSO_CALLBACK_BASE_URL`)
- finish production deploy with domains, secrets, canary smoke, and observability

## 10. External inputs required for the real SSO switch

Needed from outside `/web`:

1. `SSO_CLIENT_ID`
2. `SSO_CLIENT_SECRET`
3. callback registration for `/api/auth/sso/callback`
4. frontend/backend base URLs and allowed origins for the target environment

## 11. Files already prepared for the real SSO switch

- config templates:
  - `web/apps/admin-dashboard/backend/.env.example`
  - `web/apps/admin-dashboard/backend/.env.sso.example`
- backend provider abstraction:
  - `web/apps/admin-dashboard/backend/api/services/sso_provider.py`
- backend auth router:
  - `web/apps/admin-dashboard/backend/api/routers/auth.py`
- deploy and release docs:
  - `web/docs/admin-dashboard/DEPLOYMENT_RUNBOOK.md`
  - `web/docs/admin-dashboard/RELEASE_SMOKE_CHECKLIST.md`

## 12. Next steps

### 12.1 Immediate next step

Extract repository methods from `workspace_service.py` for:

- documents
- submissions
- reviews
- admin users
- jobs

### 12.2 After that

1. reduce `_persist_state()` full-snapshot writes
2. move sqlite persistence toward Postgres + Alembic
3. wire live ingestion if `/web` must leave contract-only mode
4. activate Google OAuth external mode in the target environment
5. rerun isolated live regression:
   - `npm run test:e2e:live`
6. manually verify:
   - student login
   - teacher login
   - admin login
   - non-compliant email denial
   - logout

## 13. Acceptance condition for final `/web` completion

`/web` is fully complete when:

1. repository methods replace direct service-layer list/dict mutation for the main workspace domains
2. production persistence and migrations are in place
3. `/web` upload and query flows are wired to the live AI/data pipeline if live mode is required
4. Google OAuth external mode is activated in the target environment
5. `uit_web_session` is still issued correctly
6. protected routes still resolve correctly by role
7. isolated live regression still passes
