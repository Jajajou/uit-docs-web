# Web Status And Plan

Last updated: 2026-04-13

## Muc do hoan thien hien tai

- Frontend: pilot-ready, live BFF-ready
- Backend `/web`: pilot-ready cho role noi bo, production hardening chua xong
- Storage: normalized persistence complete
- OAuth: code-complete, env-dependent
- Live AI path:
  - `teacher/admin`: chat + upload live da chay duoc
  - `guest/student`: da co public-safe grounded chat path dua tren catalog tai lieu cong khai

## Checklist da hoan thanh

- [x] Chot role contract `guest | student | teacher | admin`
- [x] UI shell moi cho chat, upload, manager
- [x] Login Google-only cho UIT
- [x] Dark mode, light mode, polish login/chat/admin
- [x] Frontend unit test, e2e mock, e2e live, visual, a11y, WebKit smoke
- [x] Backend security regression, auth regression, upload/review/documents regression
- [x] Normalize persistence cho:
  - [x] `sessions`
  - [x] `issued_session_tokens`
  - [x] `pending_sso_states`
  - [x] `admin_users`
  - [x] `submissions`
  - [x] `reviews`
  - [x] `jobs`
  - [x] `documents`
  - [x] `role_policies`
  - [x] `system_settings`
  - [x] `audit_logs`
  - [x] `dense_audit_logs`
  - [x] `conversations`
- [x] Bo blob state (`BLOB_STATE_KEYS = ()`)
- [x] Bo `_persist_state()` full-snapshot trong `workspace_service`
- [x] Postgres + Alembic scaffold
- [x] Postgres smoke test that khi service san sang
- [x] Google OAuth external flow code-complete
- [x] Portal overview wire vao analytics endpoints
- [x] Upload live `multipart/form-data`
- [x] Upload gateway stage -> ingest -> cleanup
- [x] Teacher/admin live chat qua LightRAG
- [x] Guest/student public-safe grounded chat path
- [x] Codebase summary file cho frontend
- [x] Codebase summary file cho backend

## Kiem tra nhanh hien tai

- Backend `python -m pytest -q --tb=short`: PASS, `68 passed, 1 skipped`
- Frontend `npm run test:coverage`: PASS, `89` tests
- Frontend `npm run test:e2e`: PASS, `15` tests
- Frontend `npm run test:e2e:webkit`: PASS, `2` tests
- Frontend `npm run test:e2e:live`: PASS, `7` tests
- Frontend `npm run build`: PASS
- Frontend `3000`: dang chay
- Backend `8001/health`: healthy
- LightRAG `9622/health`: healthy
- Qdrant `6336/healthz`: healthy

## Tinh trang van de con lai

- [ ] Bat live retrieval co audience filtering that cho `guest/student`
  - hien tai guest/student da co grounded public-doc chat, nhung chua query truc tiep live LightRAG theo visibility filter that
- [ ] Tach `InMemoryWorkspaceService` thanh repository/domain modules ro rang hon
  - hien da bo snapshot persistence, nhung business logic van tap trung trong mot service lon
- [ ] Chot production deploy that
  - domains
  - HTTPS
  - secrets
  - cookie secure
  - CORS/trusted hosts
- [ ] Hoan thien observability
  - request tracing
  - runtime dashboards
  - release smoke/runbook production
- [ ] Toi uu bundle asset login
  - anh login van nang hon mong muon

## Thu tu thuc hien de xuat

1. Bat public/student live chat chi khi da co filter visibility that
2. Tach service lon thanh repository/domain slices nho hon
3. Chot env/deploy production
4. Them observability va release smoke production
