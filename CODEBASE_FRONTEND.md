# Web Frontend Codebase

## Muc tieu

Frontend cua admin dashboard cung cap 3 mat giao dien chinh:
- `student`: chi chat
- `teacher`: chat va tai lieu noi bo
- `admin`: chat, tai lieu va quan tri he thong

UI hien tai da chuyen sang shell xanh trang cua UIT, co light mode, dark mode, Google-only auth flow, chat drawer theo huong canvas gon, va test matrix day du cho unit, e2e, visual va a11y.

## Thu muc chinh

- `web/apps/admin-dashboard/frontend/src/app`
  - bootstrap app, providers, route config, styles
- `web/apps/admin-dashboard/frontend/src/layouts`
  - shell chung, auth layout, role shell
- `web/apps/admin-dashboard/frontend/src/pages`
  - page-level route cho auth, portal, manager
- `web/apps/admin-dashboard/frontend/src/features`
  - `chat`, `uploads`, `documents`, `admin`, `auth`
- `web/apps/admin-dashboard/frontend/src/entities`
  - API clients, analytics, auth/session/types, preferences, chat/submissions/documents mappers
- `web/apps/admin-dashboard/frontend/src/shared`
  - UI primitives/composites, utilities, table/select/filter controls
- `web/apps/admin-dashboard/frontend/e2e`
  - Playwright mock/live, a11y, visual, mobile, WebKit smoke
- `web/apps/admin-dashboard/frontend/src/test`
  - Vitest unit/integration cho logic va router

## Entry points

- `src/main.tsx`
  - mount React app
- `src/app/router/AppRouter.tsx`
  - route tree chinh
- `src/app/config/routes.tsx`
  - route metadata, role gating, lazy modules
- `src/layouts/AppLayout.tsx`
  - header tabs, theme toggle, shell cho chat/upload/admin

## Auth va role model

- Frontend role contract: `guest | student | teacher | admin`
- Login page chi giu Google OAuth
- Session/current user duoc hydrate tu backend `/api/auth/*`
- Route guard:
  - `student` vao chat/public documents
  - `teacher` vao upload
  - `admin` vao manager

## Cac module quan trong

- `features/chat`
  - canvas chat chinh, lich su toggle, sidebar `Nguon tai lieu`
  - `teacher/admin` da goi live LightRAG qua backend
  - `guest/student` da di qua public-safe grounded chat path dua tren catalog tai lieu cong khai cua `/web`
- `entities/analytics`
  - query hooks va API client cho `/api/analytics/overview`, `/pipeline`, `/health`, `/graph-stats`
- `pages/portal/PortalOverviewPage.tsx`
  - dashboard tong quan da lay du lieu that tu analytics endpoints
- `features/uploads`
  - upload goc `text/url/file`, form tieng Viet, state validation
  - live file upload da di bang `multipart/form-data` khi chay BFF that
- `features/documents`
  - library/detail public-safe, redaction UI cho nguon noi bo
- `features/admin`
  - user role management, filter bar, bang admin, system settings

## Theme va UX

- Font hien tai uu tien `Be Vietnam Pro`
- Light mode theo xanh trang UIT
- Dark mode theo tone xanh duong dam, contrast cao hon, card co depth ro hon
- Dropdown, table, button, input da duoc dong bo style va focus state

## Bien moi truong can nho

- `VITE_ENABLE_MOCKS`
  - `false` de chay live BFF
- `VITE_API_BASE_URL`
  - dung cho deploy, local dev chu yeu dung Vite proxy

## Luu y runtime live

- Chat request timeout rieng hien la `90000ms`
- Upload request timeout rieng hien la `90000ms`
- Frontend local phu thuoc backend `/web` song song o `127.0.0.1:8001`
- Khi browser van giu bundle cu, can `Ctrl + F5` sau khi restart Vite de tranh gap timeout/message cu

## Lenh thuong dung

Tai `web/apps/admin-dashboard/frontend`:

```powershell
cmd /c npm.cmd run build
cmd /c npm.cmd run check
cmd /c npm.cmd run check:ci
cmd /c npm.cmd run test:e2e
cmd /c npm.cmd run test:e2e:live
cmd /c npm.cmd run test:e2e:a11y
cmd /c npm.cmd run test:e2e:visual
cmd /c npm.cmd run test:e2e:webkit
```

## Tinh trang hien tai

- UI/UX da o muc pilot-ready
- Test pyramid frontend da kha day du
- `npm run test:coverage`: PASS, `89` tests
- `npm run test:e2e`: PASS, `15` tests
- `npm run test:e2e:live`: PASS, `7` tests
- `npm run test:e2e:webkit`: PASS, `2` tests
- `npm run build`: PASS
- `npm run check:ci` khong con bi fail gia do `test:e2e:live` tranh chap backend local; Playwright live da reuse FE/BE local khi can
- Con phu thuoc backend `/web` cho auth, documents, upload, admin va chat live
- `run_backend_live.py` local mac dinh buoc backend vao `Postgres + LIVE_INGESTION_MODE=true + LightRAG local` de FE co the smoke duoc stack that
- Khi deploy that, frontend nen di qua custom domain va backend URL on dinh thay vi proxy local
