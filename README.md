# uit-docs-web

Web-only stack of the UIT Docs Agent monorepo: admin dashboard frontend (React 19 + Vite),
admin dashboard backend (FastAPI + Pydantic v2), CI/CD workflows, deploy scripts, and
the runbook.

## Layout

```
.github/workflows/        GitHub Actions: CI gates, build/publish, deploy, releases
.kiro/specs/              Spec, design, requirements (cicd-deploy-admin-dashboard)
deploy/systemd/           uit-admin-dashboard + watchdog units
docker-compose.yml        Production source of truth (reference)
docs/runbooks/            Operator runbook (admin-dashboard.md)
scripts/
  ci/                     Lockfile guard, coverage gate, alembic round-trip
  deploy/                 ssh_deploy.sh, rollback.sh
  lib/                    compute_backoff.sh
  ops/                    configure_branch_protection.sh
  smoke_test.sh           Post-deploy smoke probes
  supervisor_watchdog.sh  Restart-loop backoff
web/apps/admin-dashboard/
  backend/                FastAPI app + alembic + tests
  frontend/               React 19 + Vite + Storybook + Playwright
```

## Production deployment (free tier)

| Layer    | Platform                | Notes                                                |
|----------|-------------------------|------------------------------------------------------|
| Frontend | Vercel                  | `vercel.json` rewrites `/api/*` to backend.          |
| Backend  | Render Web Service      | Dockerfile-based, free 750h/month. Sleeps after 15m. |
| Postgres | Neon                    | Serverless free 0.5GB.                               |
| Upstream | Cloudflare Tunnel       | Public HTTPS for LangGraph (Tailscale).              |

See `docs/runbooks/admin-dashboard.md`.

## Quick start

Backend:

    cd web/apps/admin-dashboard/backend
    python -m venv .venv && .venv\Scripts\activate
    pip install -r requirements.txt -r requirements-dev.txt
    alembic upgrade head
    uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

Frontend:

    cd web/apps/admin-dashboard/frontend
    npm ci
    npm run dev

## Status

Spec `cicd-deploy-admin-dashboard` — see `.kiro/specs/cicd-deploy-admin-dashboard/`.
