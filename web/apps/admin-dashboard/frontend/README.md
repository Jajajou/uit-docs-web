# Admin Dashboard Frontend

React 19 + Vite + Tailwind v4 app rebuilt around a foundation-first architecture:

- `1 app, 3 shells`: `Public`, `Portal`, `Admin`
- route guards driven by `Session.user.role`
- shared contracts, DTO mappers and query hooks
- mock-first data layer
- internal design system with Storybook

## Source Structure

```text
src/
  app/
    config/
    guards/
    providers/
    router/
    styles/
  entities/
    auth/
    chat/
    documents/
    jobs/
    reviews/
    submissions/
  features/
    auth/
    chat/
    documents/
    jobs/
    navigation/
    review/
    submissions/
    uploads/
  layouts/
  pages/
    admin/
    auth/
    portal/
    public/
    system/
  mocks/
    fixtures/
    scenarios/
  shared/
    api/
    lib/
    ui/
  test/
```

## Commands

```bash
npm install
npm run dev
npm run typecheck
npm run lint
npm run test
npm run test:e2e
npm run test:e2e:live
npm run build
npm run storybook
npm run build-storybook
npm run check
```

## Tooling Decisions

- Server state: `@tanstack/react-query`
- Form foundation: `react-hook-form` + `zod`
- Mock contracts: local axios mock adapter is the active `/web` strategy; browser MSW startup is intentionally disabled
- UI/state: `zustand` only for chrome/session switching
- Tests: `vitest` + `@testing-library/react`
- Component catalog: Storybook

## Development Notes

- Public routes live under `/` and `/chat`
- Internal routes live under `/portal/*`
- Admin-only routes live under `/admin/*`
- Guest/student bootstrap and shell role switching pass through `/auth/callback`, which calls `/api/auth/bootstrap` in local/mock flows
- Live internal sign-in now starts at `/api/auth/sso/start`, returns through `/api/auth/sso/callback`, and lands back on frontend `/auth/callback`
- Playwright E2E runs the frontend in mock-backed mode with `VITE_ENABLE_MOCKS=true`
- Live Playwright regression runs the frontend with the mock adapter off and starts the `/web` backend BFF locally
- Browser mock mode in `/web` is axios-adapter-only; there is no active MSW worker bootstrap path and no direct `msw` app dependency in the manifest
- The live `/web` SSO kickoff currently uses a backend-owned provider emulator so lecturer/operator/admin flows remain fully testable without systems outside `/web`
- Build artifacts such as `dist/` and `storybook-static/` are ignored at the app level
