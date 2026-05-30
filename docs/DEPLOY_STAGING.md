# Staging deployment runbook â€” uit-docs-web

End-to-end checklist for bringing **Vercel frontend + Render backend** online
against `Jajajou/uit-docs-web/web_implement_split` on free tiers (no credit
card required). One operator should expect **~45 min** for the first run.

The infrastructure layout:

```
[user browser]  ->  Vercel (frontend, static SPA + edge rewrites)
                       |
                       +-- /api/*    -> Render Web Service (FastAPI backend)
                                                |
                                                +-- DATABASE_URL  -> Neon Postgres (free 0.5 GB)
                                                +-- LANGGRAPH_URL -> Cloudflare Tunnel
                                                                          |
                                                                          v
                                                                  Tailscale tailnet
                                                                  jajajou-bro.tail402a6.ts.net
```

The free tier knobs you should know about up front:

* Render web service sleeps after 15 min of idleness. First request after
  sleep takes 30-60 s. Configure cron-job.org (free) to ping `/health`
  every 10 min.
* Neon Postgres has 0.5 GB of storage and pauses idle compute. The pause is
  transparent for the app; first request after pause adds ~1 s.
* `trycloudflare.com` URLs are randomised every time the tunnel restarts.
  Re-paste the new URL into Render whenever you restart cloudflared.

## Phase 4a â€” Provision Neon Postgres

1. Sign up at https://neon.tech (Google sign-in is fine).
2. Create a new project named `uit-docs` in `Asia/Singapore`.
3. Open the **Connection Details** card and copy the *pooled* connection
   string. It looks like:

   ```
   postgresql://USER:PASS@ep-xxx-xxx-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require
   ```

   The pooled endpoint matters because Render's free dyno only gets one
   `psycopg2` connection at a time and the pooler avoids exhausting the
   per-branch limit on Neon's side.
4. Save the connection string in your password manager. You will paste it
   into Render twice (`WORKSPACE_DATABASE_URL` and `DATABASE_URL`).

## Phase 4b â€” Run the Cloudflare Tunnel locally

1. Install cloudflared on the machine that is **already joined to the
   Tailscale tailnet** (typically your laptop):

   ```sh
   winget install --id Cloudflare.cloudflared          # Windows
   brew install cloudflared                            # macOS
   ```

2. Confirm the upstream is reachable from your laptop:

   ```sh
   curl -I https://jajajou-bro.tail402a6.ts.net/ok
   ```

   Expect HTTP 200. If it fails, run `tailscale up` and re-check.

3. Start the quick-tunnel:

   ```sh
   bash scripts/ops/start_cloudflared_tunnel.sh
   ```

   Within a few seconds the output prints a line like:

   ```
   INF |  https://something-random.trycloudflare.com
   ```

   Copy that URL â€” it is your `LANGGRAPH_URL` for Render.

4. Leave this terminal running. The tunnel only stays up while
   cloudflared is alive. If you reboot or kill the process, restart
   the script and re-paste the new URL into Render.

## Phase 4c â€” Deploy the Render backend

### Option A â€” Blueprint (recommended, IaC)

1. In the Render dashboard click **New -> Blueprint**.
2. Connect the GitHub repo `Jajajou/uit-docs-web`.
3. Pick branch **`web_implement_split`**.
4. Render reads `render.yaml` at the repo root and proposes
   `uit-docs-web` with the Dockerfile at
   `web/apps/admin-dashboard/backend/Dockerfile`.
5. Click **Apply**. The build runs (5-8 min on the free tier).
6. While the build runs, open the service page and add the secrets that
   render.yaml leaves as `sync: false`. Use the values from Phase 4a/4b:

   | Variable                  | Value                                                                  |
   |---------------------------|------------------------------------------------------------------------|
   | `WORKSPACE_DATABASE_URL`  | Neon pooled connection string                                          |
   | `DATABASE_URL`            | Neon pooled connection string (same as above)                          |
   | `LANGGRAPH_URL`           | `https://something-random.trycloudflare.com` from Phase 4b             |
   | `LANGGRAPH_PUBLIC_URL`    | same as `LANGGRAPH_URL`                                                |
   | `LANGGRAPH_UPSTREAM_URL`  | same as `LANGGRAPH_URL`                                                |
   | `LANGGRAPH_API_KEY`       | leave empty for staging                                                |
   | `LANGGRAPH_PUBLIC_API_KEY`| leave empty for staging                                                |
   | `LIGHTRAG_URL`            | leave empty for staging (live ingestion stays off)                     |
   | `CORS_ORIGINS`            | `https://uit-docs-web.vercel.app,https://*.vercel.app`                 |
   | `CORS_ALLOWED_ORIGINS`    | same as `CORS_ORIGINS`                                                 |
   | `TRUSTED_HOSTS`           | `uit-docs-web.onrender.com,uit-docs-web.vercel.app,localhost,127.0.0.1` |
   | `SESSION_COOKIE_DOMAIN`   | leave empty (Render gives you a `*.onrender.com` host that the SPA on Vercel proxies through) |
   | `SSO_CLIENT_ID`           | leave empty (`ENABLE_DEMO_AUTH=true` covers staging logins)            |
   | `SSO_CLIENT_SECRET`       | leave empty                                                            |
   | `SSO_HOSTED_DOMAIN`       | `gm.uit.edu.vn`                                                        |
   | `SSO_CALLBACK_BASE_URL`   | `https://uit-docs-web.onrender.com`                                |
   | `SSO_FRONTEND_BASE_URL`   | `https://uit-docs-web.vercel.app`                                      |
   | `SSO_GROUP_ROLE_MAP`      | leave empty                                                            |
   | `GOOGLE_OAUTH_CLIENT_ID`  | leave empty (alias for `SSO_CLIENT_ID`)                                |
   | `GOOGLE_OAUTH_CLIENT_SECRET` | leave empty                                                         |
   | `LIGHTRAG_USERNAME`       | leave empty (skipped when `LIGHTRAG_URL` is empty)                     |
   | `LIGHTRAG_PASSWORD`       | leave empty                                                            |
   | `LIGHTRAG_API_KEY`        | leave empty                                                            |
   | `LIGHTRAG_PUBLIC_URL`     | leave empty                                                            |
   | `LIGHTRAG_PUBLIC_USERNAME`| leave empty                                                            |
   | `LIGHTRAG_PUBLIC_PASSWORD`| leave empty                                                            |

7. Click **Manual Deploy -> Clear build cache & deploy** so the new envs
   take effect.
8. The first deploy runs `alembic upgrade head` (CMD in Dockerfile) and
   then `uvicorn api.main:app`. Watch the logs until `Application startup
   complete` appears.

### Option B â€” Manual (skip if Blueprint worked)

1. **New -> Web Service**, connect the same repo.
2. Pick branch `web_implement_split`.
3. Root directory: `web/apps/admin-dashboard/backend`.
4. Runtime: Docker. Render auto-detects the Dockerfile.
5. Plan: Free.
6. Add the env vars from the table above PLUS the constants encoded in
   `render.yaml`'s `value:` lines (ENV, PYTHONUNBUFFERED, FORCE_HTTPS_REDIRECT, etc.).
7. Health check path: `/health`.
8. Click **Create Web Service**.

### Backend smoke test

Once Render reports the service is *Live*:

```sh
BACKEND="https://uit-docs-web.onrender.com"

# 1. Liveness probes
curl -fsS "${BACKEND}/health"   # legacy: {"status":"healthy", ...}
curl -fsS "${BACKEND}/healthz"  # new: {"status":"ok"}

# 2. Auth bootstrap (demo mode is on in staging)
curl -fsS "${BACKEND}/api/auth/me" | jq .

# 3. Confirm chat sessions endpoint (BFF auth path)
curl -fsS \
  -H 'x-test-role: student' \
  -H 'x-request-id: smoke-001' \
  "${BACKEND}/api/chat/sessions" | jq .

# 4. Streaming chat â€” confirm the BFF reaches LangGraph through the tunnel
#    (returns 200 with a JSON envelope; the live LangGraph stream surfaces
#    via SSE inside the response body)
curl -fsS -N \
  -X POST \
  -H 'Content-Type: application/json' \
  -H 'x-test-role: student' \
  -H 'x-request-id: smoke-002' \
  -d '{"message":"smoke test"}' \
  "${BACKEND}/api/chat/stream" | head -c 512
```

If `/api/chat/stream` returns 502, the LangGraph upstream is unreachable
from Render â€” re-check the Cloudflare Tunnel URL.

## Phase 3 â€” Deploy the Vercel frontend

1. Open https://vercel.com/new.
2. Click **Import Project** and pick `Jajajou/uit-docs-web`.
3. Branch: `web_implement_split`.
4. Project settings:
   * Framework: **Vite** (auto-detected by `vercel.json`).
   * Root directory: `web/apps/admin-dashboard/frontend`.
   * Build command: `npm run build` (auto).
   * Output directory: `dist` (auto).
5. Environment variables â€” leave **`VITE_API_BASE_URL`** UNSET. The SPA
   falls back to `/api`, which `vercel.json` rewrites onto the Render
   backend so the browser sees the same origin and CORS preflights are
   skipped entirely.

   The only var worth setting in Production is:
   * `VITE_ENABLE_MOCKS` â€” leave UNSET in staging/prod (default: live API).

6. Click **Deploy**. Vercel runs `npm ci` + `npm run build`. The first
   build takes ~3 min on the free tier.
7. Once the deployment is *Ready*, copy the production URL â€” it is
   either `https://uit-docs-web.vercel.app` (the canonical alias) or a
   `*-jajajou.vercel.app` deployment-specific URL. Set the canonical
   alias under **Settings -> Domains** if you have not already.
8. **Update Render**: paste the canonical Vercel URL into the
   `CORS_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `TRUSTED_HOSTS`, and
   `SSO_FRONTEND_BASE_URL` env vars on Render, then redeploy
   uit-docs-web so the trusted-host middleware accepts the new
   origin.

### Frontend smoke test

```sh
FRONTEND="https://uit-docs-web.vercel.app"
BACKEND="https://uit-docs-web.onrender.com"

# 1. SPA loads
curl -fsS "${FRONTEND}/" | grep -q '<div id="root"></div>' && echo "OK: SPA shell"

# 2. Vercel proxy to backend works (no CORS preflight)
curl -fsS "${FRONTEND}/api/auth/me" | jq .

# 3. End-to-end smoke through scripts/smoke_test.sh
bash scripts/smoke_test.sh \
  --frontend-url "${FRONTEND}" \
  --backend-url  "${BACKEND}" \
  --upstream-url "$(grep -F LANGGRAPH_URL render.yaml.values 2>/dev/null || echo https://YOUR-TUNNEL.trycloudflare.com)"
```

In the browser:

1. Visit `${FRONTEND}/`. The shell should render with no console errors.
2. Click **Log in with demo account** (staging has `ENABLE_DEMO_AUTH=true`)
   â€” the SPA hits `/api/auth/login/demo` which Vercel proxies onto Render.
3. Open the chat panel and send a message. The first request streams
   from `/api/student/runs/stream` -> Render -> Cloudflare Tunnel ->
   LangGraph and returns within 30 s when warm.

## Phase 5 â€” Keep-warm cron

Render's free tier sleeps after 15 min idle. Use cron-job.org:

1. Sign up at https://cron-job.org (free, no credit card).
2. New cronjob:
   * URL: `https://uit-docs-web.onrender.com/health`
   * Schedule: every 10 minutes
   * Notifications: e-mail on failure
3. Save. The first ping wakes the dyno; subsequent pings keep it warm.

## Phase 6 â€” Trigger CI workflows so branch protection becomes available

GitHub Actions check names only appear in the branch protection picker
*after* the workflows have run at least once. To register
`frontend-ci`, `backend-ci`, and `langgraph-ci`:

1. Locally, on `web_implement_split`:

   ```sh
   git checkout web_implement_split
   git commit --allow-empty -m "chore(ci): trigger workflows for branch protection registration"
   git push origin web_implement_split
   ```

2. Wait ~5 min and confirm three workflow runs appear at
   https://github.com/Jajajou/uit-docs-web/actions.
3. Now apply branch protection:

   * Owner-side (Jajajou): `bash scripts/ops/setup_uit_docs_web_protection.sh`
   * Or via the web UI under **Settings -> Branches**, picking the three
     check names that now appear in the dropdown.

4. The three CI gates apply to both `main` and `web_implement_split` per
   user direction. Production deploys still need a separate gate (see
   `production-deploy.yml` once it is rewritten for Render in Phase 6).

## Rollback

* **Frontend**: in Vercel, **Deployments -> Promote** an older successful
  deployment to Production. Atomic, no downtime.
* **Backend**: in Render, **Manual Deploy -> Deploys**, click the
  `Rollback` action on a known-good earlier deploy. Render recreates the
  container from the previous image. Database migrations are **not**
  rolled back automatically â€” if you bumped a schema, run
  `alembic downgrade <prev>` over Render's shell first.

## Troubleshooting cheat-sheet

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `502 Bad Gateway` on `/api/student/runs/stream` | LangGraph URL wrong | Re-run cloudflared, paste new URL into Render env, redeploy |
| `400 Trusted host invalid` from backend | Vercel host not in `TRUSTED_HOSTS` | Add `*.vercel.app` and the canonical alias to `TRUSTED_HOSTS`, redeploy |
| `CORS preflight blocked` | Browser is calling backend directly | Re-check `vercel.json` rewrites; the SPA must use `/api` (no `VITE_API_BASE_URL`) |
| `Timed out connecting to Postgres` | Neon paused + Render free dyno cold start | First request can take ~3 s; retry once. Configure cron-job.org so the dyno never cold-starts |
| `psycopg2.OperationalError: SSL connection failed` | Neon connection string missing `sslmode=require` | Append `?sslmode=require` to both `WORKSPACE_DATABASE_URL` and `DATABASE_URL` |
| Render build fails on `pip install psycopg2-binary` | Missing build deps | Already solved by Dockerfile (`apt-get install gcc libpq-dev`); if you forked the Dockerfile, restore those lines |
