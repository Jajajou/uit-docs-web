# Web Backend Codebase

## Muc tieu

Backend `/web` la BFF cua admin dashboard. No cung cap:
- Google OAuth session flow
- role enforcement `guest | student | teacher | admin`
- contract cho chat, documents, uploads, reviews, jobs, admin users, settings
- public-safe redaction cho document/citation surface
- persistence normalized cho toan bo workspace state

## Thu muc chinh

- `web/apps/admin-dashboard/backend/api/main.py`
  - FastAPI app, middleware, headers, error handling
- `web/apps/admin-dashboard/backend/api/routers`
  - route layer cho `auth`, `chat`, `documents`, `uploads`, `reviews`, `jobs`, `admin`, `analytics`
- `web/apps/admin-dashboard/backend/api/services`
  - auth helpers, fixtures, workspace service, persistence store, ingestion gateway, sso provider
- `web/apps/admin-dashboard/backend/api/clients`
  - LightRAG HTTP client
- `web/apps/admin-dashboard/backend/api/dependencies.py`
  - wiring runtime cho config, workspace store, service, ingestion gateway
- `web/apps/admin-dashboard/backend/tests`
  - pytest suite cho auth, security, uploads, reviews, documents, workspace store, alembic, postgres smoke

## Runtime model hien tai

- `InMemoryWorkspaceService`
  - van la business/service layer trung tam
  - khong con `_persist_state()`, `_bind_state()`, `_reload_state()`
  - moi mutation di qua CRUD methods cua `WorkspaceStateStore`
  - van la service lon, chua tach thanh nhieu repository/domain service nho hon
- `SqlAlchemyWorkspaceStore`
  - persistence that cho workspace state
  - da normalize tat ca domain sang bang rieng
  - ho tro SQLite local va Postgres/Alembic path
- `IngestionGateway`
  - stage file/text, goi LightRAG khi `LIVE_INGESTION_MODE=true`
  - mock-safe khi chay local contract mode

## Persistence hien tai

Store can thiep o `api/services/workspace_store.py`.

Tat ca domain da co bang rieng:
- `sessions`
- `issued_session_tokens`
- `pending_sso_states`
- `admin_users`
- `submissions`
- `reviews`
- `jobs`
- `documents`
- `role_policies`
- `system_settings`
- `audit_logs`
- `dense_audit_logs`
- `conversations`

Hien trang:
- `BLOB_STATE_KEYS = ()`
- legacy blob migration da xong
- SQLite local co the `create_all()`
- Postgres thi di qua Alembic

## Auth va phan quyen

- External auth mode: Google OAuth
- Domain restriction: `@gm.uit.edu.vn`
- `sso_provider.py`
  - token exchange
  - userinfo fetch
  - hosted domain validation
- User moi mac dinh duoc tao voi role `student`
- `admin` moi duoc nang role `teacher/admin`
- Cookie/session duoc issue qua backend

## Chat va ingestion live

- `teacher/admin`
  - chat co the di qua live LightRAG query that
- `guest/student`
  - da dung public-safe grounded chat path dua tren catalog `public + approved/archived`
  - khong query truc tiep LightRAG cho den khi co audience filter that
- Upload live:
  - `POST /api/uploads/file/multipart`
  - backend stage file vao `UPLOAD_STAGING_DIR`
  - goi gateway ingest
  - cleanup file staging trong `finally`
  - cap nhat `submission` va `job` sang `indexing`/`failed`
- Text/url upload van di qua contract rieng, co the day qua gateway khi bat live mode

## Bien moi truong quan trong

- `WORKSPACE_DATABASE_URL`
  - SQLite local hoac Postgres cho workspace persistence
- `WORKSPACE_AUTO_SEED`
  - seed state neu DB trong
- `LIVE_INGESTION_MODE`
  - bat live chat/upload path cho role noi bo
- `UPLOAD_STAGING_DIR`
  - noi luu file staging tam
- `LIGHTRAG_URL`
- `LIGHTRAG_USERNAME`
- `LIGHTRAG_PASSWORD`
- `SSO_PROVIDER_MODE`
  - `external` de bat Google OAuth that; `emulator` de dung local provider
- `SSO_CLIENT_ID`
- `SSO_CLIENT_SECRET`
- `SSO_CALLBACK_BASE_URL`
- `SSO_FRONTEND_BASE_URL`
- `run_backend_live.py`
  - dev runner local mac dinh bat `ENABLE_DEMO_AUTH=true`
  - dong thoi set `WORKSPACE_DATABASE_URL` -> Postgres `admin_dashboard`, `LIVE_INGESTION_MODE=true`, `LIGHTRAG_URL=http://127.0.0.1:9622`

## Lenh thuong dung

Tai `web/apps/admin-dashboard/backend`:

```powershell
C:\Users\hoang\anaconda3\python.exe -m pytest -q --tb=short
C:\Users\hoang\anaconda3\python.exe -m pytest tests --cov --cov-report=term-missing
C:\Users\hoang\anaconda3\python.exe run_backend_live.py
```

## Tinh trang hien tai

- Backend `/web` da co persistence that voi normalized tables cho toan bo workspace
- Service layer da bo full-snapshot persistence cu
- Security co headers, auth rate limit va redaction public surface
- Google OAuth external flow da code-complete, nhung van env-dependent
- Teacher/admin chat da co live LightRAG path
- Guest/student chat da co public-safe grounded path tu catalog tai lieu cong khai
- Upload live da co multipart + staging + ingest tracking + cleanup
- Qdrant healthcheck compose da duoc sua de phan anh dung runtime that
- Backend tests hien tai: `68 passed, 1 skipped`
  - smoke Postgres that se `skip` neu local Postgres chua mo

## Viec con lai uu tien cao

- Tach `InMemoryWorkspaceService` thanh repository/domain modules ro rang hon
- Bat live retrieval that cho `guest/student` chi khi co visibility filtering that
- Chot hardening production cho Postgres, OAuth, LightRAG va deploy
- Hoan thien observability/runtime tracing
