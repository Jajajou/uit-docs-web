# Frontend UX Audit And Plan

Status: REVIEWED DRAFT  
Date: 2026-04-18  
Scope: `web/apps/admin-dashboard/frontend` only  
Out of scope: backend contracts, crawler, RAG logic, persistence

## 0. Design Review Addendum

Reviewed against the new constraint:

- keep the current design language
- keep the main page structure and layout model
- do not do a broad IA reset in the first implementation pass
- allow changes to brittle elements such as loaders, buttons, navigation items, and startup dependencies

Implication for implementation:

- the first phase is now a shell-stability pass
- larger routing and homepage changes are deferred
- visual changes should feel like a refinement of the current product, not a redesign

## 1. Goal

Turn the current admin-dashboard frontend into a modern, reliable, easy-to-use UIT experience that:

- boots reliably on real networks
- gives students a clear task-first entry point
- keeps chat as a strong workspace instead of forcing it to be the only homepage
- makes document discovery visible and trustworthy
- feels lighter, calmer, and more intentional on desktop and mobile

## 2. Inputs Used

- Live browser audit with Playwright against:
  - `http://127.0.0.1:3000/`
  - `http://127.0.0.1:3001/` with `VITE_ENABLE_MOCKS=true`
- Frontend code audit of:
  - `index.html`
  - `src/app/config/routes.tsx`
  - `src/app/router/AppRouter.tsx`
  - `src/layouts/AppLayout.tsx`
  - `src/layouts/AuthLayout.tsx`
  - `src/pages/public/HomePage.tsx`
  - `src/pages/auth/LoginPage.tsx`
  - `src/features/chat/ChatWorkspace.tsx`
  - `src/features/documents/DocumentLibrary.tsx`
  - `src/shared/ui/composites/BrandLoadingAnimation.tsx`
  - `src/app/styles/index.css`
- Project status alignment from:
  - `web/docs/admin-dashboard/WEB_PROJECT_MASTER_STATUS.md`

## 3. Executive Summary

The current frontend has a strong component foundation, but it is not ready for UX polish-first work because there is a real P0 usability regression at app boot:

- In real browser usage, the app opens to a blank page.
- Playwright found `#root` present but empty in both normal mode and mock mode.
- The document shell loads, but React never mounts.

The strongest root cause is in `index.html`: a remote `unpkg` module for `dotlottie-wc` is loaded before `/src/main.tsx`. If that third-party script is slow or stalls, the main app bootstrap is delayed behind it, which leaves the site blank.

Even after that is fixed, the product still needs follow-up frontend UX work:

- `/` routes directly into chat instead of a useful homepage
- `HomePage.tsx` exists but is unused
- the document library is a major feature but is hidden from primary navigation
- the visual language is competent but over-indexed on glass, blur, and "dashboard chrome" instead of task clarity

The right direction is not "more decoration." It is:

1. make the shell unbreakable
2. separate landing/discovery from conversation
3. make task entry obvious
4. simplify the visual system so trust and speed win over ornament

## 4. Live Playwright Findings

### 4.1 P0 blank-page regression

Observed in live usage:

- Playwright opened the app and found:
  - page title present
  - `document.body` containing only `#root` and scripts
  - `#root` still empty
- `snapshot` returned an empty rendered tree
- full-page screenshot timed out while waiting for fonts

Interpretation:

- the HTML shell is delivered
- the React app is not mounting
- the runtime is blocked before the UI becomes usable

### 4.2 Boot is coupled to third-party network health

`index.html` currently loads:

- Google Fonts from `fonts.googleapis.com`
- a remote module script from `unpkg.com`
- a Lottie asset dependency path through `lottie.host`

The critical issue is the ordering:

- remote `dotlottie-wc` module is loaded before `/src/main.tsx`

That creates a fragile startup path for the entire app.

### 4.3 Mock mode does not protect the shell

Even when the app is started with `VITE_ENABLE_MOCKS=true`, Playwright still sees a blank root. This means the problem is not backend dependence first. The shell itself is unstable before feature-level UX can be evaluated.

## 5. Code Audit Findings

### 5.1 Routing and IA are misaligned

Evidence:

- `AppRouter.tsx` sends `/` directly to `ChatPage`
- `HomePage.tsx` exists but is not routed

Impact:

- the app lacks a safe, lightweight landing surface
- first-time users are dropped into the heaviest workspace immediately
- chat is forced to serve as both homepage and tool, which weakens both roles

### 5.2 Documents are underexposed

Evidence:

- `routeMeta` includes `/documents`
- `AppLayout.tsx` hardcodes `workspaceNav` to only `Chat`, `Upload`, `Manager`

Impact:

- one of the most trust-building parts of the product is effectively hidden
- users cannot discover the library naturally from top-level navigation
- citation-driven reading exists, but browsing and verification are not first-class

### 5.3 Loading UX is visually polished but operationally brittle

Evidence:

- `BrandLoadingAnimation.tsx` depends on custom element `dotlottie-wc`
- the element depends on a remote module loaded globally from `index.html`
- the animation source itself is also remote

Impact:

- the fallback meant to reassure users becomes the reason the app can fail to render
- the product has no resilient low-tech loading state

### 5.4 Visual system is attractive but too “glassy” for the product job

Evidence:

- heavy use of blur, glow, radial gradients, glossy cards, and soft glass surfaces across layouts
- `HomePage`, `AuthLayout`, `AppLayout`, and admin surfaces all lean on similar visual effects

Impact:

- hierarchy feels softer than it should
- the shell looks premium, but task scanning is slower than necessary
- admin tooling and student guidance are visually too close together

### 5.5 Typography and asset loading are unnecessarily fragmented

Evidence:

- `index.html` loads `Inter`
- `index.css` imports `Be Vietnam Pro`
- both are remote

Impact:

- extra startup cost for two font strategies
- screenshot/perf flakiness becomes more likely
- typography feels less intentional because the system has two competing defaults

### 5.6 Design artifacts have drifted from status docs

Evidence:

- `WEB_PROJECT_MASTER_STATUS.md` references `web/design/admin-dashboard/uxui_screen`
- current `web/design` path does not exist

Impact:

- the project lacks an active source of truth for target-state UI
- frontend polish decisions are more likely to drift or regress

## 6. Product Framing (Office Hours Lens)

### 6.1 Who is desperate for this?

The most urgent users are students who need immediate answers to high-stakes academic questions:

- hoc phi
- dang ky hoc phan
- lich hoc vu
- chuong trinh dao tao
- hoc bong
- tai lieu va quy dinh lien quan

Secondary users:

- teachers uploading or verifying internal materials
- admins handling user roles and internal governance

### 6.2 What is the status quo?

Today, users do one of these:

- ask friends/class groups
- search scattered official pages
- read forum posts or outdated screenshots
- guess from prior semesters

The frontend should beat the status quo by being:

- faster than searching the web
- clearer than chat threads
- more trustworthy than screenshots

### 6.3 What is the narrowest winning wedge?

Not "AI chat for everything."

The winning wedge is:

`A trusted UIT task desk that lets students start from a concrete task, then choose between quick answers, official documents, and role-specific actions.`

That means the homepage should not be the chat transcript. The homepage should be the decision surface.

## 7. North Star UX Direction

The frontend should feel like a modern campus operations desk:

- calm, confident, and clear
- official but not bureaucratic
- fast even on imperfect networks
- obvious on first use
- deeper only when the user asks for depth

Working design direction:

- background: warm ivory plus UIT blue and slate, not pure white dashboard chrome
- cards: stronger borders, less glass, fewer ambient glows
- typography: one main family, one weight system, tighter hierarchy
- motion: mostly route and content transitions, not decorative motion loops
- navigation: obvious task categories before deep workflow tools

## 8. Target Information Architecture

Note:

- this section remains the long-range direction
- it is not part of the first implementation pass under the current constraint

### 8.1 Public routes

- `/` -> task-first landing page
- `/chat` -> conversation workspace
- `/documents` -> document library
- `/documents/:id` -> evidence-first detail page
- `/auth/login` -> login

### 8.2 Internal routes

- `/upload` -> contributor upload workspace
- `/manager` -> admin workspace

### 8.3 Global nav principles

- always show `Hoi nhanh`
- always show `Tai lieu`
- only show `Tai len` for teacher/admin
- only show `Quan tri` for admin
- make current location obvious
- keep mobile nav shallow

## 9. Recommended Frontend Plan

### Phase 0. Stabilize the shell

Goal: make the app always render usable UI before any backend or animation dependency matters.

Work:

- remove all critical-path third-party scripts from `index.html`
- move Lottie dependency out of document bootstrap
- replace `BrandLoadingAnimation` with:
  - CSS/SVG loader as default
  - optional rich animation after mount only
- use one font strategy only
- make the landing shell render with zero backend requirements

Acceptance:

- Playwright sees non-empty `#root`
- screenshot succeeds
- app still renders with blocked `unpkg` and `lottie.host`
- current layout and visual identity remain recognizably the same

### Phase 1. Reset the IA

Goal: separate orientation from execution.

Status:

- deferred by current design constraint
- do not implement in the first pass

Work:

- route `/` to `HomePage`
- keep `/chat` as dedicated workspace
- add `Documents` into primary nav
- define a homepage with:
  - top urgent tasks
  - quick links to chat prompts
  - recent official updates
  - clear split between public lookup and internal actions

Acceptance:

- first-time user can tell where to start in under 5 seconds
- document library is reachable in one click from the top nav

### Phase 2. Refresh the chat workspace

Goal: make chat feel like a trustworthy tool, not a visually busy experiment.

Work:

- reduce chrome around the message area
- surface reference quality, freshness, and confidence more clearly
- keep quick prompts but align them with real student tasks
- make history and reference rails calmer and easier to scan
- improve empty-state onboarding for first question

Acceptance:

- users can distinguish summary, warnings, and source evidence instantly
- mobile chat remains usable without hidden critical actions

### Phase 3. Upgrade library and document detail

Goal: make official documents feel discoverable and verifiable.

Work:

- elevate filters and search as first-class controls
- make status, issuing unit, and update time easier to scan
- improve document detail hierarchy:
  - summary
  - citation metadata
  - scope/effectiveness
  - related sources
- add cleaner reading width and better metadata grouping

Acceptance:

- users can decide whether a document is relevant in one glance
- “official source” trust is visually stronger than today

### Phase 4. Tune role-based surfaces

Goal: make teacher and admin tools feel operationally focused, not cosmetically related to student chat.

Work:

- simplify admin chrome
- increase density where useful
- make teacher upload flow more guided and less dashboard-like
- differentiate internal workspace tone from public/student tone

Acceptance:

- teacher/admin screens feel purpose-built
- public screens do not look like admin tools

### Phase 5. Lock mobile and accessibility

Goal: make the experience dependable on real student devices.

Work:

- define mobile nav behavior
- reduce sticky header footprint
- check tap targets, overflow, and drawer states
- improve contrast in light and dark modes
- reduce motion for users who prefer it

Acceptance:

- critical flows pass at 360px, 768px, and 1440px
- no critical content is hidden behind hover-only or wide-screen-only patterns

## 10. File-Level Frontend Backlog

### Highest-leverage files

- `web/apps/admin-dashboard/frontend/index.html`
- `web/apps/admin-dashboard/frontend/src/shared/ui/composites/BrandLoadingAnimation.tsx`
- `web/apps/admin-dashboard/frontend/src/app/router/AppRouter.tsx`
- `web/apps/admin-dashboard/frontend/src/layouts/AppLayout.tsx`
- `web/apps/admin-dashboard/frontend/src/pages/public/HomePage.tsx`
- `web/apps/admin-dashboard/frontend/src/features/chat/ChatWorkspace.tsx`
- `web/apps/admin-dashboard/frontend/src/features/documents/DocumentLibrary.tsx`
- `web/apps/admin-dashboard/frontend/src/pages/public/DocumentDetailPage.tsx`
- `web/apps/admin-dashboard/frontend/src/pages/auth/LoginPage.tsx`
- `web/apps/admin-dashboard/frontend/src/app/styles/index.css`

## 11. Success Metrics

### Reliability

- app shell renders without external animation dependency
- homepage visible in under 2 seconds on local dev
- blank-page regression covered by Playwright

### UX clarity

- new user reaches either Chat or Documents within one click
- document library becomes a discoverable top-level feature
- homepage communicates what the product is for without reading dense copy

### Performance

- no critical render blocked by third-party script
- fewer remote assets on first paint
- lighter fallback states

## 12. Test Strategy

### Playwright checks

- homepage renders visible hero and task grid
- chat route renders shell and composer
- documents route renders filter/search/table
- login route renders without external blocking dependency
- admin route renders in mock mode

### Visual checks

- desktop wide
- laptop
- mobile portrait
- dark mode and light mode

### Regression checks

- block `unpkg.com` and confirm app still mounts
- block `lottie.host` and confirm fallback still renders
- disable Google Fonts and confirm layout still holds

## 13. GSTACK Review Report

### CEO review

Decision: APPROVE with scope sharpening

Reason:

- the right product is not “prettier chat”
- the right product is “trusted task desk”
- homepage, evidence, and task-entry clarity matter more than extra UI embellishment

### Eng review

Decision: APPROVE

Reason:

- phase order is correct
- shell resilience must come before design polish
- plan stays frontend-only and does not depend on backend changes

### Design review

Decision: APPROVE with preservation constraint

Constraint:

- reduce blur, glow, and ornamental loading motion
- increase hierarchy, contrast, and scan speed
- preserve the current shell composition and overall visual language

### DX review

Decision: SKIP

Reason:

- this plan is user-facing product UI, not a developer-facing experience

## 14. Final Approval Gate

The following choices should be treated as locked for the next frontend implementation pass:

- `Yes`: preserve the current main layout and design language
- `Yes`: remove third-party script dependency from initial app bootstrap
- `Yes`: replace fragile rich loading animation with resilient local fallback
- `Yes`: keep phase 1 scoped to shell stability and zero-backend boot reliability
- `No`: do not reroute `/` away from chat in this pass
- `No`: do not perform a broad navigation or homepage redesign in this pass

## 15. Companion Artifact

A static concept HTML that captures the target direction lives at:

- `web/docs/admin-dashboard/prototypes/modern-campus-desk-concept.html`

This is not production code. It is the visual and IA target for the next implementation pass.
