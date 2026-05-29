# Admin Dashboard App

Workspace app cho phần web nội bộ của UIT Docs Agent.

## Architecture

```text
apps/admin-dashboard/
  backend/              # FastAPI middleware
  frontend/             # React 19 + Vite app
  docker-compose.yml    # Local app orchestration
  README.md
```

## Frontend Structure

```text
frontend/src/
  app/
    providers/
    router/
    styles/
  layouts/
  pages/
    auth/
    dashboard/
    documents/
    upload/
  shared/
    ui/
```

## Related Workspace Folders

- Docs: `web/docs/admin-dashboard/WEB_PROJECT_MASTER_STATUS.md`
- Design references: `web/design/admin-dashboard/uxui_screen`

## Quick Start

### Development

```bash
# Backend
cd backend
cp .env.example .env
uv pip install -e .
uvicorn api.main:app --reload --port 8001

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

### Docker

```bash
docker compose up -d
```

## API Endpoints

See `backend/README.md` for full API documentation.

## Tech Stack

- Backend: FastAPI, Python 3.11+
- Frontend: React 19, Vite, Tailwind v4
- UI: Radix UI, Framer Motion, Lucide Icons
