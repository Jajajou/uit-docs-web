# Admin Dashboard Runbook

This runbook covers deployment, rollback, secrets, and on-call procedures
for the UIT admin dashboard stack (`admin_backend`, `admin_frontend`,
`lightrag_uit`). It is the single source of truth for operators and is
referenced from `.kiro/specs/cicd-deploy-admin-dashboard/requirements.md`.

## Required Secrets

All secrets are stored exclusively in the GitHub Actions Secret Store
(Requirement 13.1) and must be rotated on a cadence of **at most 90 days**
(Requirement 13.2). Secret values are never written to logs, image
filesystems, or build args; CI surfaces them as `***` automatically.

| Secret | Purpose | Owner | Rotation cadence |
|---|---|---|---|
| `LANGGRAPH_UPSTREAM_URL` | Base URL of the LangGraph upstream service consumed by `admin_backend` (initially the Tailscale endpoint, later a managed/self-hosted LangGraph deployment). Read at startup; required for `e2e-live` and all deploy workflows. | `<devops-lead@example.com>` | ≤ 90 days |
| `VERCEL_TOKEN` | Authenticates the Vercel CLI used by `staging-deploy.yml` and `production-deploy.yml` to deploy `admin_frontend` previews and the production project. | `<devops-lead@example.com>` | ≤ 90 days |
| `STAGING_SSH_HOST` | Hostname or IP of the staging docker-compose host used by `scripts/deploy/ssh_deploy.sh`. | `<devops-lead@example.com>` | ≤ 90 days (rotate when the host is rebuilt) |
| `STAGING_SSH_USER` | UNIX account under which `docker compose pull && docker compose up -d` is executed on the staging host. | `<devops-lead@example.com>` | ≤ 90 days |
| `SSH_PRIVATE_KEY` | OpenSSH private key authorized on both `STAGING_SSH_HOST` and `PROD_SSH_HOST` for the deploy user. Written to `${{ runner.temp }}` only and removed by an `if: always()` cleanup step (Requirement 13.4). | `<security-lead@example.com>` | ≤ 90 days; rotate immediately on any operator offboarding |
| `PROD_SSH_HOST` | Hostname or IP of the production docker-compose host used by `scripts/deploy/ssh_deploy.sh` from `production-deploy.yml`. | `<devops-lead@example.com>` | ≤ 90 days (rotate when the host is rebuilt) |
| `PROD_SSH_USER` | UNIX account under which production deploys execute. | `<devops-lead@example.com>` | ≤ 90 days |
| `DEPLOY_FAILURE_WEBHOOK_URL` | Notification webhook (Slack/Teams/Discord-compatible) posted to within 2 minutes of any failed staging or production deploy (Requirement 9.6). | `<oncall-rotation@example.com>` | ≤ 90 days |
| `LIGHTRAG_API_KEY` | API key used by `admin_backend` to authenticate to `lightrag_uit`. | `<devops-lead@example.com>` | ≤ 90 days |
| `GOOGLE_OAUTH_CLIENT_ID` | OAuth client identifier for admin sign-in. | `<security-lead@example.com>` | ≤ 90 days |
| `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth client secret paired with the client ID above. | `<security-lead@example.com>` | ≤ 90 days; rotate immediately on suspected exposure |
| `POSTGRES_DSN` | PostgreSQL connection string for `admin_backend` and Alembic migrations. | `<dba@example.com>` | ≤ 90 days |
| `JWT_SECRET` | HMAC signing key for admin session JWTs. | `<security-lead@example.com>` | ≤ 90 days; rotate immediately on suspected exposure (sessions invalidated on rotation) |

Replace each `<owner@example.com>` placeholder with the real owner email or
group alias before promoting this runbook to production. When rotating a
secret, update the value in the GitHub Actions Secret Store, re-run the
relevant deploy workflow, and record the rotation date in the team's
secret-rotation log.

## LangGraph Upstream

The admin backend depends on a single LangGraph upstream service for agent
orchestration. Per Requirement 14.1 the URL is read **only** from the
`LANGGRAPH_UPSTREAM_URL` environment variable at startup; there is no
hard-coded fallback.

### Current upstream

| Field | Value |
|---|---|
| Current value | `https://jajajou-bro.tail402a6.ts.net` (Tailscale endpoint) |
| Secret name | `LANGGRAPH_UPSTREAM_URL` |
| Migration target classification | managed or self-hosted LangGraph deployment |
| Date of last update | `<YYYY-MM-DD — replace on every secret rotation>` |

The current Tailscale endpoint is exposed as a public funnel. If the
upstream is moved back to a tailnet-only endpoint, confirm the staging and
production deploy hosts are joined and that `tailscale status` reports the
endpoint as `idle` or `active` before deploying.

### Contract surface

A migration target must implement the following endpoints with semantics
identical to the current upstream (Requirement 15.3). Conformance is
verified by running the existing `admin_backend` client against the new
URL without source changes. See `docs/api/langgraph-api-hl.md` for request
and response examples.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/ok` | Stable liveness probe used by `e2e-live.yml` and `scripts/smoke_test.sh`. Must return HTTP 2xx within 5 seconds when healthy. |
| `GET` | `/info` | Service metadata and runtime information. |
| `POST` | `/assistants/search` | Discover RetrievalGraph and IndexGraph assistants. Body: `{}`. |
| `POST` | `/runs/wait` | Synchronous RetrievalGraph query or IndexGraph command execution. |
| `POST` | `/runs/{run_id}/resume` | Resume IndexGraph human-in-the-loop metadata review. |
| `GET` | `/threads/{thread_id}/history` | Inspect conversation or indexing thread history. |

### How to swap the upstream

Per Requirement 15.2, swapping the upstream is a **secret-only change**.
Do not rebuild images, edit code, or change deploy artifacts.

1. Verify the new endpoint contract:

   ```sh
   curl --max-time 5 -fsS "${NEW_UPSTREAM_URL}/ok"
   curl --max-time 30 -fsS -X POST "${NEW_UPSTREAM_URL}/assistants/search" \
     -H 'content-type: application/json' -d '{}'
   curl --max-time 120 -fsS -X POST "${NEW_UPSTREAM_URL}/runs/wait" \
     -H 'content-type: application/json' \
     -d '{
       "assistant_id": "5bbc8364-e383-5087-8a2f-b6d27677f7a1",
       "input": {
         "messages": [
           {
             "role": "user",
             "content": "What is the UIT Docs Agent?"
           }
         ]
       },
       "config": {
         "configurable": {
           "thread_id": "runbook-smoke"
         }
       }
     }'
   ```

   All calls must return HTTP 2xx (Requirement 15.4). Record the outcome
   in this runbook's "Date of last update" field.

2. Update the `LANGGRAPH_UPSTREAM_URL` secret in the GitHub Actions Secret
   Store (repository Settings → Secrets and variables → Actions).

3. Re-run `staging-deploy.yml` and confirm the smoke test passes against
   the new URL.

4. Promote to production by re-running `production-deploy.yml` (or by
   pushing a new `v*` tag on a fresh image).

5. If the staging probe or smoke test fails, revert the secret to the
   previously known-good value within 15 minutes (Requirement 15.5).

## Rollback

The Rollback_Procedure restores the previously deployed image tags for
`admin_backend`, `admin_frontend`, and `lightrag_uit`, and runs
`alembic downgrade` to the previously deployed migration revision
(Requirements 9.5, 12.6, 12.8, 15.1, 18.5).

The rollback record is `/etc/uit-docs/deployment.json` on the deploy
host, written by `scripts/deploy/ssh_deploy.sh` only on a successful
deploy. It contains the new and previous image tags and the new and
previous Alembic revisions.

### Automated rollback (preferred)

`production-deploy.yml` and `staging-deploy.yml` invoke
`scripts/deploy/rollback.sh` automatically on any smoke-test failure
(within 10 minutes for staging, immediately for production). The script
restores `previous_image_tag` and runs
`alembic downgrade <previous_alembic_revision>`.

To invoke the rollback manually from an operator workstation that has
SSH access to the deploy host:

```sh
# Production
ssh "${PROD_SSH_USER}@${PROD_SSH_HOST}" \
  'sudo /opt/uit/scripts/deploy/rollback.sh --compose-file /opt/uit/docker-compose.yml'

# Staging
ssh "${STAGING_SSH_USER}@${STAGING_SSH_HOST}" \
  'sudo /opt/uit/scripts/deploy/rollback.sh --compose-file /opt/uit/docker-compose.yml'
```

### Manual rollback steps

Use this sequence only when `rollback.sh` is unavailable (for example,
the deployment record is missing or corrupt). Run from the deploy host
as the deploy user.

1. Read the previous deployment record:

   ```sh
   cat /etc/uit-docs/deployment.json
   # Note previous_image_tag and previous_alembic_revision.
   ```

2. Revert the `admin_backend` and `lightrag_uit` image tags by writing
   the previous tag to `/opt/uit/.env` and reloading the stack:

   ```sh
   sudo sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=${PREVIOUS_TAG}/" /opt/uit/.env
   sudo chmod 600 /opt/uit/.env
   docker compose -f /opt/uit/docker-compose.yml pull
   docker compose -f /opt/uit/docker-compose.yml up -d admin_backend lightrag_uit
   ```

3. Revert the `admin_frontend` Vercel deployment by promoting the prior
   production deployment from the Vercel dashboard
   (Project → Deployments → previous production build → "Promote to
   Production"), or via the CLI:

   ```sh
   vercel rollback "${PREVIOUS_VERCEL_DEPLOYMENT_URL}" \
     --token "${VERCEL_TOKEN}" --yes
   ```

4. Downgrade the Alembic revision (Requirement 12.6, 12.8):

   ```sh
   docker compose -f /opt/uit/docker-compose.yml exec admin_backend \
     alembic downgrade "${PREVIOUS_ALEMBIC_REVISION}"
   ```

   If the downgrade exits non-zero, **halt the rollback**, retain the
   current database state, and page the on-call engineer (Requirement
   12.8). Do not attempt a second downgrade without DBA review.

5. Re-run the smoke test to confirm restoration:

   ```sh
   bash scripts/smoke_test.sh \
     --frontend-url "https://${PROD_FRONTEND_DOMAIN}" \
     --backend-url  "https://${PROD_BACKEND_DOMAIN}" \
     --upstream-url "${LANGGRAPH_UPSTREAM_URL}"
   ```

6. Open a post-incident ticket and attach the failed deploy's workflow
   run URL, the rollback log output, and the diff of
   `/etc/uit-docs/deployment.json` before and after the rollback.

## On-call

This section lists the URLs and routes the on-call engineer needs to
triage a production incident (Requirements 17.4, 17.6, 18.6).

### Health and metrics endpoints

| Surface | URL | Expected response |
|---|---|---|
| `admin_backend` health | `https://<PROD_BACKEND_DOMAIN>/healthz` | `200 {"status":"ok"}` when the LangGraph circuit breaker is `Closed` or `HalfOpen`; `503` with `Structured_Error{code:"LANGGRAPH_UNAVAILABLE"}` when `Open`. |
| `admin_frontend` health | `https://<PROD_FRONTEND_DOMAIN>/` | `200` HTML root. |
| LangGraph upstream health | `${LANGGRAPH_UPSTREAM_URL}/ok` | `200` within 5 seconds. |
| Prometheus metrics | `https://<PROD_BACKEND_DOMAIN>/metrics` | `200` text exposition format within 2 seconds (Requirement 17.6). |

### Alert routing

| Alert | Source | Page target |
|---|---|---|
| Circuit breaker `Open` (`langgraph_circuit_state == 1`) for ≥ 5 minutes | Prometheus rule on `/metrics` | `<oncall-primary-pager@example.com>` |
| `admin_backend` `/healthz` returning 503 for ≥ 2 minutes | External uptime monitor | `<oncall-primary-pager@example.com>` |
| Restart-loop watchdog backoff active (`uit-supervisor-watchdog.service` log line `backoff_active=true`) | journald → log aggregator | `<oncall-secondary-pager@example.com>` |
| Deploy workflow concluded `failure` | `DEPLOY_FAILURE_WEBHOOK_URL` (posted by `staging-deploy.yml` / `production-deploy.yml`) | `<devops-channel@example.com>` |
| Smoke test failed during deploy | Same webhook as above | `<devops-channel@example.com>` (escalates to primary pager after 15 minutes) |

Replace each `<...@example.com>` placeholder with the real pager target
or rotation alias before activating alert routing.

### Smoke-test failure response

A failed smoke test from `staging-deploy.yml` or `production-deploy.yml`
indicates the post-deploy state is unhealthy. The workflow has already
invoked `scripts/deploy/rollback.sh` automatically (Requirement 9.5,
11.2). On-call response (Requirement 17.4):

1. Open the failed workflow run from `DEPLOY_FAILURE_WEBHOOK_URL`. Note
   the failed component name, the stage, and the workflow run URL.
2. Confirm `/healthz` for `admin_backend`, `/` for `admin_frontend`, and
   `/ok` for the LangGraph upstream are all 2xx after the automatic
   rollback. If not, follow the manual rollback steps above.
3. Check `/metrics` for `langgraph_circuit_state` and
   `langgraph_upstream_failures_total{kind=...}`. If the circuit is
   `Open`, treat it as an upstream incident and follow the LangGraph
   Upstream procedure to swap the URL or wait for upstream recovery.
4. If the rollback itself failed, page the secondary on-call and DBA.
   Do not retry the deploy until the host is healthy.
5. File a post-incident report linking the workflow run, the smoke-test
   `Structured_Error` line, and the rollback log within 24 hours.

## Operator Commands

### Install the boot unit (uit-admin-dashboard.service)

The `uit-admin-dashboard.service` unit brings the docker-compose stack
up at `multi-user.target` so the dashboard recovers automatically after
a host reboot (Requirement 17.2). Install it once per host:

```
sudo install -m 0644 deploy/systemd/uit-admin-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now uit-admin-dashboard.service
```

Verify the unit is healthy:

```
systemctl status uit-admin-dashboard.service
journalctl -u uit-admin-dashboard.service -n 200
```

The unit reads runtime configuration (including `IMAGE_TAG`) from
`/opt/uit/.env` via `EnvironmentFile=-/opt/uit/.env`. The leading `-`
makes the file optional so the unit will start on a freshly
provisioned host before `scripts/deploy/ssh_deploy.sh` writes
`/opt/uit/.env` on the first successful deploy. CD-driven deploys
update `/opt/uit/.env` and then re-run `docker compose up -d` directly,
so no unit restart is required for tag changes.

To override env values for ad-hoc operator use without editing
`/opt/uit/.env`, create a drop-in:

```
sudo systemctl edit uit-admin-dashboard.service
# Add:
# [Service]
# Environment="IMAGE_TAG=v1.2.3"
sudo systemctl daemon-reload
sudo systemctl restart uit-admin-dashboard.service
```

The unit uses `Type=oneshot` with `RemainAfterExit=yes`, so a healthy
unit reports `active (exited)` after `docker compose up -d` returns.
`TimeoutStopSec=45s` leaves a 15-second margin above the compose-level
`stop_grace_period: 30s` so containers receive SIGTERM and finish
shutting down before SIGKILL (design C11, R16.6/R16.7).

### Install the restart-loop watchdog (uit-supervisor-watchdog.timer)

The watchdog timer enforces quadratic restart-loop backoff per
Requirement 16.8. Install alongside the boot unit:

```
sudo install -m 0755 scripts/supervisor_watchdog.sh /usr/local/bin/uit-supervisor-watchdog.sh
sudo install -m 0644 deploy/systemd/uit-supervisor-watchdog.service /etc/systemd/system/
sudo install -m 0644 deploy/systemd/uit-supervisor-watchdog.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now uit-supervisor-watchdog.timer
```

Verify the timer is firing every 30 seconds:

```
systemctl list-timers uit-supervisor-watchdog.timer
journalctl -u uit-supervisor-watchdog.service -n 200
```

### Standard operator commands

Day-to-day commands for inspecting and recovering the docker-compose
stack on the deploy host (Requirements 17.4, 18.5, 18.6). All commands
target `/opt/uit/docker-compose.yml` (the production source of truth per
Requirement 16.1).

#### Service status

```sh
docker compose -f /opt/uit/docker-compose.yml ps
```

Success indicator: every service is listed with `State: running` (or
`Up`), and services with healthchecks (`admin_backend`, `admin_frontend`)
report `(healthy)` after the 30-second `start_period`. A service in
`(unhealthy)` or `Restarting` state requires investigation.

#### Tail recent logs

```sh
docker compose -f /opt/uit/docker-compose.yml logs --tail=200 <service>
# Examples:
docker compose -f /opt/uit/docker-compose.yml logs --tail=200 admin_backend
docker compose -f /opt/uit/docker-compose.yml logs --tail=200 -f admin_frontend
```

Success indicator: the most recent lines show steady-state activity
(structured request log lines for `admin_backend`, nginx access lines
for `admin_frontend`) without repeating tracebacks. Logs are rotated
via the `json-file` driver at `max-size=20m`, `max-file=5`
(Requirement 17.1).

#### Restart a single service

```sh
docker compose -f /opt/uit/docker-compose.yml restart <service>
```

Success indicator: the command exits 0 and a follow-up `ps` shows the
service back in `Up (healthy)`. If the service immediately re-enters
`Restarting`, the host watchdog (`uit-supervisor-watchdog.timer`) will
apply the quadratic backoff defined in Requirement 16.8 — do not loop
on `restart` manually.

#### Exec into a running container

```sh
docker compose -f /opt/uit/docker-compose.yml exec admin_backend sh
docker compose -f /opt/uit/docker-compose.yml exec admin_backend \
  alembic current
docker compose -f /opt/uit/docker-compose.yml exec admin_backend \
  python -m app.scripts.healthcheck
```

Use `exec` for read-only diagnostics (DB connectivity, Alembic state,
config dump). Avoid mutating container state via `exec`; use a deploy
or a rollback instead.

#### Pull a new image and reload

```sh
docker compose -f /opt/uit/docker-compose.yml pull
docker compose -f /opt/uit/docker-compose.yml up -d
```

Success indicator: `pull` reports `Pulled` (or `up to date`) for every
service, and `up -d` reports `Started` for any service whose digest
changed. Containers without digest changes are left running.

#### Stop the stack

```sh
docker compose -f /opt/uit/docker-compose.yml down
```

Success indicator: every container exits cleanly within the
`stop_grace_period: 30s` window. The systemd boot unit
`uit-admin-dashboard.service` will bring the stack back up on the next
boot.

## Production Configuration

This section captures the production values that must be present in
`/opt/uit/.env` and the `production` GitHub Environment for
`production-deploy.yml` to succeed (Requirement 20.8).

### Domains and routing

| Field | Production value (placeholder) | Notes |
|---|---|---|
| Admin frontend domain | `https://<PROD_FRONTEND_DOMAIN>` | Served by Vercel; HTTP requests are 308-redirected to HTTPS by the Vercel project (Requirement 20.1, 20.2). Replace the placeholder with the actual production hostname before promoting. |
| Admin backend domain | `https://<PROD_BACKEND_DOMAIN>` | Terminated at the edge proxy in front of the docker-compose host; backend listens on port 8001 internally. |
| LangGraph upstream | `${LANGGRAPH_UPSTREAM_URL}` | See "LangGraph Upstream" section above. |

### `CORS_ALLOWED_ORIGINS`

The admin backend reads this comma-separated list at startup and
rejects any cross-origin request whose `Origin` is not in the list with
HTTP 403 (Requirement 20.4). If unset, empty, or unparseable, every
cross-origin request is rejected and a `Structured_Error` with code
`CORS_MISCONFIGURED` is logged (Requirement 20.5).

```
CORS_ALLOWED_ORIGINS=https://<PROD_FRONTEND_DOMAIN>
```

To add a second origin (for example a staging-like preview), append it
with a comma and no whitespace:
`https://<PROD_FRONTEND_DOMAIN>,https://<PREVIEW_FRONTEND_DOMAIN>`.

### `TRUSTED_HOSTS`

The admin backend reads this comma-separated list at startup and
rejects any request whose `Host` header is not in the list with HTTP 400
(Requirement 20.6), even when the `Origin` is allowed by CORS. If unset,
empty, or unparseable, every request is rejected and a `Structured_Error`
with code `TRUSTED_HOSTS_MISCONFIGURED` is logged (Requirement 20.7).

```
TRUSTED_HOSTS=<PROD_BACKEND_DOMAIN>
```

The trusted host list contains hostnames only (no scheme, no port).
Include every hostname the backend is reachable on, including any
internal load-balancer alias used by health probes.

### `ENV=production`

```
ENV=production
```

The backend keys cookie hardening on this exact string. Setting `ENV`
to anything other than `production` (including `prod`, `Production`, or
`PRODUCTION`) disables the production-only cookie attributes. CI for
production deploys writes `ENV=production` into `/opt/uit/.env`
verbatim.

### Secure cookie attributes

Whenever `ENV == "production"`, the admin backend issues authentication
cookies with the following attributes (Requirement 20.3):

| Attribute | Value | Effect |
|---|---|---|
| `Secure` | (flag set) | Browser sends the cookie only over HTTPS. |
| `HttpOnly` | (flag set) | JavaScript on the page cannot read the cookie. |
| `SameSite` | `Lax` | Cookie is sent on top-level navigations from other origins, but not on cross-site subrequests. |
| `Path` | `/` | Cookie is scoped to the entire backend origin. |

The cookie attribute summary is enforced by `app/core/security.py`
and verified by the property test in
`web/apps/admin-dashboard/backend/tests/core/test_cookies.py`. To
verify a live deploy:

```sh
curl -i -c - "https://<PROD_BACKEND_DOMAIN>/api/auth/login" -d '...'
# Expect: Set-Cookie: <name>=<value>; Path=/; Secure; HttpOnly; SameSite=Lax
```

### Container image signing (cosign)

`docker-build-publish.yml` signs every pushed image with
[cosign](https://docs.sigstore.dev/) before the workflow run is marked
successful (Requirements 7.6, 7.7). Signing happens by digest
(`ghcr.io/<owner>/<image>@sha256:...`) so the signature is bound to
the exact bytes that were pushed, regardless of how many tags point at
that digest.

**Default: keyless OIDC**

The workflow uses keyless signing backed by GitHub Actions OIDC. No
long-lived signing key is stored anywhere — cosign requests a short-
lived certificate from the Sigstore Fulcio CA using the workflow's
OIDC token, signs the digest, and records the signature in the
Sigstore Rekor transparency log. The signature artifact is also pushed
to GHCR next to the image.

Operator setup for keyless signing:

1. Ensure `permissions: id-token: write` is set on the workflow (this
   is already configured in `.github/workflows/docker-build-publish.yml`).
2. No additional GitHub repository secrets are required.
3. To verify a signature locally:

   ```
   cosign verify \
     --certificate-identity-regexp 'https://github.com/<owner>/<repo>/.github/workflows/docker-build-publish.yml@.*' \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     ghcr.io/<owner>/admin_backend@sha256:<digest>
   ```

**Alternative: key-based signing (`COSIGN_PRIVATE_KEY`)**

Use this path only when keyless OIDC is unavailable (for example, an
air-gapped runner without network access to Fulcio/Rekor, or a fork
that cannot mint OIDC tokens for the upstream repository).

1. Generate a cosign keypair locally:

   ```
   COSIGN_PASSWORD='<strong-passphrase>' cosign generate-key-pair
   ```

   This produces `cosign.key` (private) and `cosign.pub` (public).

2. Store the private key and its passphrase as GitHub Actions secrets:

   - `COSIGN_PRIVATE_KEY` — contents of `cosign.key`
   - `COSIGN_PASSWORD`    — passphrase used during key generation

   Distribute `cosign.pub` out of band so verifiers can validate
   signatures without contacting Sigstore.

3. Replace the `Sign image with cosign` step's `run:` block with:

   ```
   echo "$COSIGN_PRIVATE_KEY" > /tmp/cosign.key
   trap 'rm -f /tmp/cosign.key' EXIT
   cosign sign --key /tmp/cosign.key --yes "${IMAGE_REF}@${IMAGE_DIGEST}"
   ```

   and pass `COSIGN_PRIVATE_KEY` and `COSIGN_PASSWORD` through the
   step's `env:` block. `id-token: write` can be dropped from the
   workflow `permissions:` block when keyless is fully replaced.

4. Verify a signature using the public key:

   ```
   cosign verify --key cosign.pub ghcr.io/<owner>/admin_backend@sha256:<digest>
   ```

Rotate `COSIGN_PRIVATE_KEY` on the same ≤90-day cadence as the other
secrets in `## Required Secrets`. Re-sign existing image digests
after a rotation if downstream verifiers pin to the previous public
key.

## Branch Protection

Branch protection on `main` enforces the merge-blocking guarantees of
Requirements 2.7, 3.4, 4.4, and 5.1–5.4: a pull request can only merge
into `main` after the three quality-gate workflows conclude `success`,
the PR has at least one approving review, and every review thread is
resolved.

GitHub branch protection is repository configuration that lives outside
the source tree. This repository ships **two** ways to configure it; pick
whichever fits your operational model. Both produce the same on-GitHub
state.

### Declared state (the source of truth)

| Setting | Value | Why |
|---|---|---|
| Branch | `main` | The only protected branch (R5.2). |
| Required status checks | `frontend-ci`, `backend-ci`, `langgraph-ci` | Quality gates required by R2.7, R3.4, R4.4. Names match the `name:` field of each workflow YAML, kept in sync via `tests/cicd/workflow_registry.py`. |
| Strict status checks | `true` | Head ref must be up to date with `main` so the required checks run on the post-merge tree. |
| Required approving reviews | `1` | Minimum one human approval before merge. |
| Dismiss stale reviews on new commits | `true` | New commits invalidate prior approvals (R5.2). |
| Require conversation resolution | `true` | No unresolved review threads at merge time. |
| Enforce for admins | `true` | Admins cannot bypass the rules. |
| Allow force pushes | `false` | History on `main` is append-only. |
| Allow deletions | `false` | The branch cannot be deleted. |

When a required workflow run concludes `failure` or `cancelled`, GitHub
disables the merge button until the failed check has been re-run with
conclusion `success` or superseded by a new commit on the head branch
(R5.2). While a required check is still in progress, the merge button is
blocked unless the repository's auto-merge setting permits it (R5.3).

### Option A — apply with `scripts/ops/configure_branch_protection.sh`

The bash script wraps the GitHub REST endpoint
`PUT /repos/{owner}/{repo}/branches/{branch}/protection` and is
idempotent: re-running it converges the live state to the declared
state. Use this for one-off bootstrap and for post-incident corrections.

Prerequisites:

- `gh` (GitHub CLI) and `jq` installed and on `PATH`.
- `GH_TOKEN` (or an authenticated `gh` session) with admin permissions
  on the target repository. Branch protection is an admin-only API.

Apply to the current repository's `main` branch:

```sh
GH_TOKEN=$(gh auth token) \
  scripts/ops/configure_branch_protection.sh
```

Apply to a different repository or branch explicitly:

```sh
scripts/ops/configure_branch_protection.sh \
  --repo <owner>/<repo> \
  --branch main
```

Preview the API call without making it (useful in CI dry-runs):

```sh
scripts/ops/configure_branch_protection.sh --dry-run
```

The script derives `<owner>/<repo>` from `git remote get-url origin` when
`REPO` is unset, fails fast on missing dependencies (`gh`, `jq`), and
exits non-zero with a `Structured_Error`-style message on API failure.

### Option B — declare via `.github/branch-protection.yml`

If the repository runs the [probot/settings](https://github.com/repository-settings/app)
GitHub App (or a compatible alternative such as
[`repo-config`](https://github.com/jasonetco/repo-config)), the same
declared state lives in `.github/branch-protection.yml` at the repo
root. The app reconciles the file on every push to `main`, so the
configuration is reviewed and rolled forward like any other change.

Operator setup:

1. Install the `probot/settings` (or equivalent) GitHub App on the
   repository with `Administration: Read & Write` permission.
2. Merge `.github/branch-protection.yml` to `main`. The app applies the
   configuration on the next push.

Either option satisfies the same requirements; the script is preferred
for ad-hoc corrections, the YAML is preferred when the repository is
managed declaratively.

### Verifying the live state

After applying, confirm the live state matches the declared state:

```sh
gh api -H "Accept: application/vnd.github+json" \
  repos/<owner>/<repo>/branches/main/protection \
  | jq '{
      contexts: .required_status_checks.contexts,
      strict: .required_status_checks.strict,
      reviews: .required_pull_request_reviews.required_approving_review_count,
      dismiss_stale: .required_pull_request_reviews.dismiss_stale_reviews,
      conversation_resolution: .required_conversation_resolution.enabled,
      enforce_admins: .enforce_admins.enabled,
      allow_force_pushes: .allow_force_pushes.enabled,
      allow_deletions: .allow_deletions.enabled
    }'
```

The `contexts` array must contain exactly `frontend-ci`, `backend-ci`,
`langgraph-ci`. If a check is added or renamed (for example, when a new
required workflow is introduced under `.github/workflows/`), update both
`scripts/ops/configure_branch_protection.sh` and
`.github/branch-protection.yml` and re-run option A or push the YAML
change.
