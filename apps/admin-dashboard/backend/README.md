# Admin Dashboard Backend API

FastAPI BFF for the `/web` workspace.

Path:

- `web/apps/admin-dashboard/backend`

This backend now mirrors the frontend contract used by:

- `web/apps/admin-dashboard/frontend`

## Current scope

- In-memory BFF for `/web` only
- No live dependency on services outside `/web` during tests
- Normalized error envelope aligned with the frontend API client
- Role-aware routes with institutional email enforcement for:
  - `lecturer`
  - `operator`
  - `admin`

## Contract-aligned endpoints

### Auth

- `POST /api/auth/bootstrap`
- `GET /api/auth/sso/metadata`
- `GET /api/auth/sso/start`
- `GET /api/auth/sso/callback`
- `POST /api/auth/logout`
- `GET /api/auth/me`

### Chat

- `GET /api/chat/sessions`
- `POST /api/chat/stream`

### Uploads

- `POST /api/uploads/file`
- `POST /api/uploads/text`
- `POST /api/uploads/url`
- `POST /api/uploads/scan`

Legacy alias kept for compatibility:

- `POST /api/upload/file`
- `POST /api/upload/text`
- `POST /api/upload/url`

### Documents

- `GET /api/documents`
- `GET /api/documents/{id}`
- `POST /api/documents/{id}/archive`
- `POST /api/documents/{id}/reindex`

### Submissions

- `GET /api/submissions`
- `GET /api/submissions/{id}`

### Reviews

- `GET /api/reviews`
- `POST /api/reviews/{id}/decision`

### Jobs

- `GET /api/jobs`
- `POST /api/jobs/{id}/retry`

### Admin

- `GET /api/admin/users`
- `PATCH /api/admin/users/{id}`
- `GET /api/admin/roles`
- `GET /api/admin/settings`
- `PATCH /api/admin/settings/{key}`
- `GET /api/admin/audit-logs`

### Analytics

- `GET /api/analytics/overview`
- `GET /api/analytics/pipeline`
- `GET /api/analytics/graph-stats`
- `GET /api/analytics/health`

## Error contract

All handled failures return:

```json
{
  "error": {
    "code": "string_code",
    "message": "Human readable message",
    "status": 403,
    "requestId": "uuid-or-forwarded-id",
    "details": null
  }
}
```

The backend also propagates `x-request-id`.

## Local development

```bash
python -m pip install -e .[dev]
uvicorn api.main:app --reload --port 8001
```

Real-provider handoff template:

- `web/apps/admin-dashboard/backend/.env.sso.example`
- workspace summary:
  - `web/docs/admin-dashboard/WEB_PROJECT_MASTER_STATUS.md`

## Quality gates

Run from `web/apps/admin-dashboard/backend`:

```bash
python -m ruff check .
python -m pytest
```

Current automated backend status on `2026-03-24`:

- `ruff check` pass
- `pytest` pass, `37` tests

## Notes

- The frontend contract is the source of truth for `/web`.
- This BFF uses an in-memory workspace service so tests never need live LightRAG.
- Live `/web` auth now resolves through a cookie-backed bootstrap flow and backend-owned SSO kickoff, while `x-demo-role` remains only for mock/fallback compatibility.
- The current SSO kickoff uses a config-driven provider layer.
  - default mode is a local provider emulator inside `/web`
  - external provider mode can now reuse the same `/auth/callback` contract once real authorize URL, client id, and claim mapping are available
- Existing LightRAG client files remain in the repo, but active `/web` tests do not depend on that network path.
