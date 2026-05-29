# Implementation Plan: CI/CD and Production Deployment for Admin Dashboard

Convert the feature design into a series of prompts for a code-generation LLM that will implement each step with incremental progress. Make sure that each prompt builds on the previous prompts, and ends with wiring things together. There should be no hanging or orphaned code that isn't integrated into a previous step. Focus ONLY on tasks that involve writing, modifying, or testing code.

## Overview

This plan turns the four design pillars — root-level CI workflows, tag-and-merge-driven CD, a defensive LangGraph upstream client with a circuit breaker, and a docker-compose supervisor — into discrete coding tasks. Implementation languages follow the design: Python 3.11 for `Admin_Backend`, TypeScript/React for `Admin_Frontend`, YAML for GitHub Actions, and POSIX `bash` for deploy and smoke-test scripts. Property-based tests use Hypothesis (Python) and fast-check (TypeScript) and are placed close to the implementation they validate. Each property test is annotated with its property number and the requirement clauses it validates.

## Tasks

- [x] 1. Set up shared scaffolding for CI, deploy scripts, and runbook
  - [x] 1.1 Create root-level workflow directory and placeholder files
    - Create `.github/workflows/` at the repository root if absent.
    - Add empty placeholder YAML files `frontend-ci.yml`, `backend-ci.yml`, `langgraph-ci.yml`, `e2e-live.yml`, `docker-build-publish.yml`, `release.yml`, `staging-deploy.yml`, `production-deploy.yml`, each containing a `name:` and a no-op `on: workflow_dispatch` trigger so subsequent tasks can fill them in.
    - _Requirements: 1.1, 1.8_

  - [x] 1.2 Create deploy script and runbook scaffolding
    - Create `scripts/deploy/ssh_deploy.sh` and `scripts/deploy/rollback.sh` as executable POSIX bash stubs that print their argument list and exit 0.
    - Create `scripts/smoke_test.sh` as an executable POSIX bash stub that prints `usage` and exits 1.
    - Create `docs/runbooks/admin-dashboard.md` with empty section headers `## Required Secrets`, `## LangGraph Upstream`, `## Rollback`, `## On-call`, `## Operator Commands`, `## Production Configuration`.
    - _Requirements: 13.2, 15.1, 17.4, 18.5, 18.6, 20.8_

  - [x] 1.3 Create test directories for new CI/property tests
    - Create `tests/cicd/__init__.py`, `tests/scripts/__init__.py`, `tests/migrations/__init__.py`, and `tests/middleware/__init__.py` under `web/apps/admin-dashboard/backend/`.
    - Add a top-level `pytest.ini` entry (or extend the existing one) that registers `tests/cicd`, `tests/scripts`, `tests/migrations`, and `tests/middleware` as test paths.
    - Ensure `hypothesis` is added to `web/apps/admin-dashboard/backend/requirements-dev.txt` with an exact `==` pin.
    - _Requirements: 19.3_

- [x] 2. Implement path-filter model and triggered-workflow function
  - [x] 2.1 Implement workflow event and path-filter pure function
    - Create `tests/cicd/workflow_model.py` with the `Event` and `Workflow` dataclasses and the `matches(workflow, event) -> bool` function as defined in design data model D2.
    - Implement `triggered_workflows(event, workflows) -> set[str]` that returns the set of workflow names whose `matches()` is True.
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

  - [x] 2.2 Write property test for path-filter correctness
    - **Property 1: Path-Filter Correctness**
    - **Validates: Requirements 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8**
    - File: `tests/cicd/test_path_filter.py`. Hypothesis strategy: random subsets of a fixed `repo_files()` list across the eight workflows. Assert `triggered_workflows()` equals `{ w : path_filter(w) ∩ F ≠ ∅ ∨ path_filter(w) is empty }`. Run with `max_examples=100`.

  - [x] 2.3 Encode the eight workflow definitions used by the model
    - Add `tests/cicd/workflow_registry.py` listing the eight workflows with the exact path filters and trigger sets from design table C1, so the model and the YAML stay synchronized.
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_

- [x] 3. Author the three quality-gate CI workflows
  - [x] 3.1 Author `frontend-ci.yml`
    - Triggers: `pull_request` and `push: main` with the path filter `web/apps/admin-dashboard/frontend/**` and `.github/workflows/frontend-ci.yml`.
    - Concurrency group: `frontend-ci-${{ github.ref }}` with `cancel-in-progress: true`.
    - Sequential steps in `web/apps/admin-dashboard/frontend`: `npm ci`, `npm run lint`, `npm run typecheck`, `npm run test -- --run`, `npm run build`, `npm run test:e2e:mock`, each gated on prior `success`.
    - Upload artifacts `admin-frontend-dist-${{ github.sha }}` (contents of `dist/`, retention 14 days) and `admin-frontend-coverage-${{ github.sha }}` (coverage output, retention 14 days), each with `if: success()` on the producing step.
    - Set `timeout-minutes: 20`.
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 5.4, 19.2, 19.6_

  - [x] 3.2 Author `backend-ci.yml`
    - Triggers: `pull_request` and `push: main` with the path filter `web/apps/admin-dashboard/backend/**` and `.github/workflows/backend-ci.yml`.
    - Concurrency group: `backend-ci-${{ github.ref }}` with `cancel-in-progress: true`.
    - Working directory: `web/apps/admin-dashboard/backend`.
    - Steps in order: setup Python 3.11 with pip cache, run a lockfile-pin guard step (sub-task 3.4), install from `requirements.txt -r requirements-dev.txt`, `ruff check .`, conditional `mypy app` step gated on detection of `mypy.ini` or `[tool.mypy]` in `pyproject.toml`, `pytest --cov=app --cov-report=xml`, coverage gate (sub-task 3.5), Alembic migration check (sub-task 3.6).
    - Upload `coverage.xml` as `admin-backend-coverage-${{ github.sha }}` with `if: always()`, retention 14 days.
    - Set `timeout-minutes: 20`.
    - _Requirements: 1.1, 1.3, 3.1, 3.2, 3.3, 3.4, 3.5, 3.7, 5.4, 19.3_

  - [x] 3.3 Author `langgraph-ci.yml`
    - Triggers: `pull_request` and `push: main` with the path filter `LangGraph/**` and `.github/workflows/langgraph-ci.yml`.
    - Concurrency group: `langgraph-ci-${{ github.ref }}` with `cancel-in-progress: true`.
    - Prefer `uses: ./LangGraph/.github/workflows/unit-tests.yml` and `uses: ./LangGraph/.github/workflows/integration-tests.yml` via `workflow_call`; fall back to a single job that runs `pytest LangGraph/tests` from the repository root using the Python version declared in those internal workflows.
    - Set `timeout-minutes: 30`.
    - _Requirements: 1.1, 1.4, 4.1, 4.2, 4.3, 5.4_

  - [x] 3.4 Implement and wire backend lockfile-pin guard
    - Add `scripts/ci/check_requirements_pinned.sh` that fails non-zero if any non-comment, non-empty line in `requirements.txt` lacks `==`, naming each unpinned package on stdout. Call it from `backend-ci.yml` before `pip install`.
    - _Requirements: 19.3, 19.5_

  - [x] 3.5 Implement and wire backend coverage gate
    - Add `scripts/ci/coverage_gate.py` that parses `coverage.xml`, reads the root `line-rate` attribute, exits 0 iff it is at least `0.70`, otherwise exits 1 with an explanatory message. Call it from `backend-ci.yml` immediately after `pytest`.
    - _Requirements: 3.6_

  - [x] 3.6 Write property test for coverage gate
    - **Property 13: Coverage Gate**
    - **Validates: Requirements 3.6**
    - File: `tests/cicd/test_coverage_gate.py`. Hypothesis strategy: floats in `[0.0, 1.0]` with edge values `0.6999`, `0.70`, `0.7001`. Build a temporary `coverage.xml`, invoke the script via `subprocess.run`, assert `exit 0 ⇔ line-rate ≥ 0.70`.

  - [x] 3.7 Implement and wire backend Alembic migration check
    - Add `scripts/ci/alembic_round_trip.sh` that exports `DATABASE_URL=sqlite:///$RUNNER_TEMP/alembic_check.db`, runs `timeout 300 alembic upgrade head`, `timeout 300 alembic downgrade base`, `timeout 300 alembic upgrade head`, with `set -o pipefail` and explicit `$?` checks; the script deletes the temp DB on exit and exits non-zero on any command failure. Call it from `backend-ci.yml` after the coverage gate.
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

  - [x] 3.8 Write property test for migration round-trip
    - **Property 5: Migration Reversibility**
    - **Validates: Requirements 12.1, 12.2, 12.3, 12.4**
    - File: `tests/migrations/test_round_trip.py`. Iterate over every Alembic revision id present in `web/apps/admin-dashboard/backend/alembic/versions/` using a Hypothesis `sampled_from` strategy. For each, invoke the round-trip script against a fresh SQLite temp file and assert each command exits 0. Run with `max_examples=100` capped to revision count.

- [x] 4. Checkpoint - quality gates green
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Author the live E2E workflow and the PR status reporter
  - [x] 5.1 Author `e2e-live.yml`
    - Triggers: `schedule: '0 18 * * *'` and `workflow_dispatch`.
    - Concurrency group: `e2e-live` with `cancel-in-progress: true`.
    - Step 1: fail with annotation `LANGGRAPH_UPSTREAM_URL secret missing` if `${{ secrets.LANGGRAPH_UPSTREAM_URL }}` is empty.
    - Step 2: `curl --max-time 5 -fsS ${LANGGRAPH_UPSTREAM_URL}/health`; on non-2xx or timeout, mark Playwright job as skipped with annotation `LangGraph upstream unavailable` and exit 0.
    - Step 3 (only on probe success): run Playwright with `playwright.live.config.ts` and `timeout-minutes: 30`.
    - Always-step: upload `playwright-report` directory with retention 14 days when Playwright actually ran; preserve the distinction between `failure` (Playwright non-zero or > 30m) and the skip path.
    - _Requirements: 1.8, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [x] 5.2 Author `pr-status-summary.yml` reusable workflow
    - Trigger: `workflow_run` for each of the eight workflows in Requirement 1.1, on `completed`.
    - Post a per-workflow GitHub status via `POST /repos/{owner}/{repo}/statuses/{sha}` with `context = workflow filename without extension` and `state ∈ {success, failure}` within 30 seconds of completion.
    - Maintain exactly one summary comment authored by `github-actions[bot]` whose body starts with the marker `<!-- pr-status-summary:v1 -->`. Edit in place if found, create exactly one if not, never modify any other comment.
    - _Requirements: 21.1, 21.2, 21.3, 21.4_

  - [-] 5.3 Write property test for PR status comment idempotency
    - **Property 17: PR Status Comment Idempotency**
    - **Validates: Requirements 21.2, 21.3, 21.4**
    - File: `tests/cicd/test_pr_status.py`. Hypothesis strategy: random sequences of workflow-run completions over a mocked GitHub Issues API. Assert that after any sequence exactly one marker comment exists, its body matches the latest run, and no other `github-actions[bot]` comment was modified.

- [ ] 6. Implement Docker build, publish, signing, and reproducibility
  - [x] 6.1 Author `docker-build-publish.yml`
    - Triggers: `push: main` and `push: tags v*`.
    - Concurrency group: `docker-build-publish-${{ github.ref }}` with `cancel-in-progress: true`.
    - Matrix over `[admin_backend, admin_frontend, lightrag]` with the contexts from design C6.
    - Per slot: GHCR login via `docker/login-action@v3` with `permissions: packages: write`, retried up to 2 times on auth failure; `docker/setup-buildx-action@v3`; `docker/build-push-action@v5` with `build-args: GIT_SHA=${{ github.sha }}, BUILD_TIME=<ISO 8601 UTC>` and `secrets: <BuildKit --secret mounts only>`; tags `main, sha-${{ github.sha }}` on `push: main` and `${{ github.ref_name }}, latest` on `push: tags v*`; `provenance: true`, `sbom: true`; env `SOURCE_DATE_EPOCH=$(git show -s --format=%ct ${{ github.sha }})`.
    - On any per-slot failure, halt that slot's push and signing operations, mark the workflow run as failed with the failed image and step identified, and do not publish partially built artifacts.
    - Set `timeout-minutes: 30` per slot.
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.7, 7.8, 13.5, 19.1, 19.4_

  - [-] 6.2 Add cosign signing step
    - After successful push of an image, run `cosign sign --yes ghcr.io/<owner>/<image>@<digest>` so the signature is published to GHCR before the workflow run is marked successful. Use keyless OIDC by default; document the alternative `COSIGN_PRIVATE_KEY` path in the runbook.
    - _Requirements: 7.6, 7.7_

  - [-] 6.3 Add Trivy secret-scan step
    - On push jobs only (not PR cache builds), pull `aquasec/trivy:latest` and run `timeout 600 trivy image --scanners secret <image-ref>`; on non-zero exit or timeout, mark the workflow as failed and do not advance to the next image.
    - _Requirements: 13.6, 13.7, 13.8_

  - [-] 6.4 Add reproducibility verification job
    - Add a follow-up job `build-twice` that runs only on `push: main` and tag pushes. It rebuilds the matrix from the same commit on the same builder image with identical build args and asserts that the layer digests for the application-source layer and the dependency-install layer match between runs (compare `docker buildx imagetools inspect` output). Fail the workflow on mismatch.
    - _Requirements: 7.5, 19.1, 19.4_

  - [ ] 6.5 Write property test for build reproducibility model
    - **Property 6: Build Reproducibility**
    - **Validates: Requirements 7.5, 19.1, 19.2, 19.3, 19.4**
    - File: `tests/cicd/test_build_reproducibility_model.py`. Hypothesis strategy: random `(commit_sha, builder_version, build_args, lockfiles)` tuples passed through a deterministic-build simulator that mirrors the BuildKit input set. Assert that identical inputs produce identical synthetic layer digests, and any single field perturbation produces a different digest.

  - [x] 6.6 Implement tag-computation function and wire into workflow
    - Add `scripts/ci/compute_tags.sh` that, given an event kind (`push:main` or `push:tag`) and a ref or SHA, prints the exact tag set to stdout per design Property 12 (`{main, sha-<sha>}` or `{<ref_name>, latest}`). Call it from `docker-build-publish.yml` to feed the `tags:` input.
    - _Requirements: 7.1, 7.2_

  - [-] 6.7 Write property test for tag computation
    - **Property 12: Tag Computation**
    - **Validates: Requirements 7.1, 7.2, 7.4**
    - File: `tests/cicd/test_tag_computation.py`. Hypothesis strategy: random `(event_kind, ref, sha)` tuples drawn from `{push:main, push:tag-v*, push:tag-other}` × valid SHAs × valid tag names. Assert the output tag set per Property 12 and that `push:tag` not matching `v*` produces an empty set.

  - [-] 6.8 Write property test for secret-scan correctness
    - **Property 3: Secret Hygiene**
    - **Validates: Requirements 13.3, 13.5, 13.6, 13.7, 13.8**
    - File: `tests/cicd/test_secret_scan.py`. Hypothesis strategy: random sentinel strings drawn from a length-32 alphabet, optionally injected into a fixture image's filesystem, env, or build args. Build the image with the secret never passed via `build-args`, run the scan, assert exit code 1 ⇔ sentinel present and exit code 0 ⇔ sentinel absent.

- [ ] 7. Author the release workflow
  - [ ] 7.1 Author `release.yml`
    - Trigger: `push: tags v*`.
    - Concurrency group: `release-${{ github.ref }}`.
    - Resolve the previous matching tag with `git describe --tags --abbrev=0 --match "v*" HEAD~1 || true`; call `POST /repos/{owner}/{repo}/releases/generate-notes` with `previous_tag_name` (or empty for first release).
    - Append a fenced-code section listing `ghcr.io/<owner>/{admin_backend,admin_frontend,lightrag}:${{ github.ref_name }}`.
    - Run `gh release create ${{ github.ref_name }} --title ${{ github.ref_name }} --notes-file body.md` within 120 seconds of trigger; fail the workflow on API errors without retry; do not delete the underlying tag on failure.
    - _Requirements: 1.8, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [x] 8. Implement smoke test script and its property test
  - [x] 8.1 Implement `scripts/smoke_test.sh`
    - Parse `--frontend-url`, `--backend-url`, `--upstream-url`; on any missing or unrecognized argument, exit 1 and print exactly one `Structured_Error{code:"BAD_ARG"}` JSON line to stdout.
    - Issue three parallel `curl --max-time 5 -o /dev/null -w "%{http_code} %{time_total}"` probes to `${backend-url}/healthz`, `${frontend-url}/`, `${upstream-url}/health`; aggregate results.
    - Exit 0 only when all three probes return HTTP 200–299 and total elapsed time is at most 30 seconds; otherwise exit 1 and print exactly one `Structured_Error` line naming the failed URL, the observed status (or `timeout`/`dns_error`/`tls_error`), and `elapsed_ms`.
    - Distinguish error codes `BAD_ARG`, `SMOKE_HTTP_FAIL`, `SMOKE_TIMEOUT`, `SMOKE_DNS_ERROR`, `SMOKE_TLS_ERROR`, `SMOKE_BUDGET_EXCEEDED`.
    - _Requirements: 18.1, 18.2, 18.3, 18.4_

  - [x] 8.2 Write property test for smoke test contract
    - **Property 10: Smoke Test Contract**
    - **Validates: Requirements 18.1, 18.2, 18.3, 18.4**
    - File: `tests/scripts/test_smoke_test.py`. Hypothesis strategy: random response patterns from three local HTTP servers spun up per example, each returning a status drawn from `{200..299, 300..599, timeout, close-without-response}`. Invoke `bash scripts/smoke_test.sh` via `subprocess.run`, assert exit code and stdout JSON match Property 10.

- [ ] 9. Implement the LangGraph upstream client and circuit breaker
  - [x] 9.1 Implement `Structured_Error` envelope and config validators
    - Add `web/apps/admin-dashboard/backend/app/core/errors.py` with the `Structured_Error` Pydantic model whose `code` is constrained to the closed set in design D1.
    - Add `app/core/settings.py` Pydantic Settings that read `LANGGRAPH_UPSTREAM_URL`, `CORS_ALLOWED_ORIGINS`, `TRUSTED_HOSTS`, and `ENV`. On invalid `LANGGRAPH_UPSTREAM_URL`, raise a startup error that emits `code=LANGGRAPH_UPSTREAM_URL_MISSING` and exits non-zero before binding the HTTP port.
    - _Requirements: 14.1, 14.8, 20.4, 20.5, 20.6, 20.7_

  - [x] 9.2 Implement circuit breaker
    - Add `app/clients/circuit_breaker.py` with the `CircuitBreakerState` dataclass and a `CircuitBreaker` class implementing the rolling 60-second failure-window state machine: ≥5 failures → `Open`; in `Open`, probe every 30s; after 2 consecutive 2xx probes → `Closed`; non-2xx probe in `HalfOpen` → `Open`. Expose `state`, `allow_request()`, `on_success()`, `on_failure()`, and a `probe_loop` coroutine spawned by FastAPI `lifespan`.
    - _Requirements: 14.4, 14.5_

  - [x] 9.3 Implement `LangGraphClient` with timeouts and retry
    - Add `app/clients/langgraph.py`. Use `httpx.AsyncClient` with `httpx.Timeout(connect=5.0, read=30.0, write=30.0, pool=5.0)`. Wrap each call with `tenacity.AsyncRetrying`: max 3 attempts, `wait_exponential(multiplier=0.5, min=0.5, max=4.0)`, retry only on `httpx.ConnectError`, `httpx.ReadTimeout`, `httpx.WriteTimeout`, `httpx.PoolTimeout`, and 5xx; never retry 4xx. Update the breaker via `on_success`/`on_failure`. On exhausted retries, raise `LangGraphUnavailable` carrying a `Structured_Error{code:"LANGGRAPH_UNAVAILABLE"}` with redacted upstream URL, `elapsed_ms`, and `request_id`.
    - _Requirements: 14.2, 14.3, 14.6, 14.9, 15.2, 15.3_

  - [x] 9.4 Wire the client and breaker into FastAPI startup and shutdown
    - In `app/main.py`, instantiate the breaker and the client in `lifespan`, mount them on `app.state`, spawn the breaker probe loop, and cancel it on shutdown. Replace any existing direct `httpx` calls to LangGraph with `app.state.langgraph_client.request(...)`.
    - _Requirements: 14.1, 14.4, 14.5, 14.6, 14.9_

  - [-] 9.5 Implement `/healthz`
    - Add `app/api/health.py` exposing `GET /healthz` that returns `200 {"status":"ok"}` when the breaker state is `Closed` or `HalfOpen`, and `503` with a `Structured_Error{code:"LANGGRAPH_UNAVAILABLE"}` body when the breaker state is `Open`.
    - _Requirements: 14.7_

  - [ ] 9.6 Write property test for upstream isolation
    - **Property 4: Upstream Isolation**
    - **Validates: Requirements 14.4, 14.6, 14.9**
    - File: `tests/clients/test_langgraph_isolation.py`. Hypothesis strategy: a random failure mode ∈ `{conn_refused, dns, connect_timeout, read_timeout, http_500, http_502, http_503, http_504}` × a random route from a fixture set partitioned into `langgraph_dependent` and `non_langgraph_dependent`. Use `respx` to stub the upstream. Assert non-LG routes return 200 and LG routes return 503 + `LANGGRAPH_UNAVAILABLE`, and that the raw upstream body never appears in the response.

  - [-] 9.7 Write property test for retry policy
    - **Property 9: LangGraph Retry Policy**
    - **Validates: Requirements 14.3, 14.4, 14.5**
    - File: `tests/clients/test_retry_policy.py`. Hypothesis strategy: finite sequences of upstream outcomes drawn from `{2xx, 4xx, 5xx, conn_error, timeout}`. Stub `httpx`/time, run `LangGraphClient.request`, and assert: at most 3 attempts; immediate stop on 2xx or any 4xx; retry only on `{5xx, conn_error, timeout}`; delays in `[500ms, 4000ms]`; and the breaker transitions to `Open` after ≥5 failures in a 60-second rolling window.

  - [ ] 9.8 Write property test for health-endpoint consistency
    - **Property 7: Health-Endpoint Consistency**
    - **Validates: Requirements 14.7**
    - File: `tests/clients/test_healthz_state.py`. Hypothesis strategy: random breaker states (`Closed`, `Open`, `HalfOpen` with `success_count ∈ {0, 1}`). Drive the breaker into the chosen state, hit `/healthz`, assert the response code per Property 7.

  - [-] 9.9 Write property test for startup config validation
    - **Property 11: Config Validation at Startup**
    - **Validates: Requirements 14.1, 14.8, 20.4, 20.5, 20.6, 20.7**
    - File: `tests/core/test_startup_config.py`. Hypothesis strategy: random env-var triplets including unset, empty, malformed, and valid values. Assert (a) startup terminates with `LANGGRAPH_UPSTREAM_URL_MISSING` iff the URL is unset/empty/invalid, (b) deny-all CORS handler logs `CORS_MISCONFIGURED` iff `CORS_ALLOWED_ORIGINS` is unset/empty/unparseable, (c) deny-all trusted-host handler logs `TRUSTED_HOSTS_MISCONFIGURED` iff `TRUSTED_HOSTS` is unset/empty/unparseable.

- [x] 10. Implement production hardening middlewares and structured logging
  - [x] 10.1 Implement CORS, trusted-host, and cookie hardening
    - In `app/main.py`, install `TrustedHostMiddleware` from `TRUSTED_HOSTS` before `CORSMiddleware` from `CORS_ALLOWED_ORIGINS`. On unparseable/empty values, install deny-all handlers that return HTTP 400 / HTTP 403 respectively and log the corresponding `Structured_Error`.
    - In `app/core/security.py`, set cookie attributes `Secure; HttpOnly; SameSite=Lax; Path=/` whenever `ENV == "production"` for any authentication cookie issued by the backend.
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7_

  - [x] 10.2 Write property test for production cookie hardening
    - **Property 15: Production Cookie Hardening**
    - **Validates: Requirements 20.3**
    - File: `tests/core/test_cookies.py`. Hypothesis strategy: random cookie names and values, with `ENV ∈ {production, staging, dev}`. Issue an auth cookie via the helper, parse `Set-Cookie`, assert `Secure`, `HttpOnly`, `SameSite=Lax` are all present iff `ENV == "production"`.

  - [x] 10.3 Implement structured request log middleware
    - Add `app/middleware/request_log.py` as a single `BaseHTTPMiddleware` that emits exactly one JSON log line per request after the response, with fields `timestamp` (UTC ISO 8601), `request_id` (UUIDv4 from `X-Request-Id` or generated), `method`, `path`, `status` (integer), `duration_ms` (integer clamped to `[0, 600000]`), `user_id_hash` (SHA-256 of subject claim, empty when unauthenticated). Wire it into `app/main.py`.
    - _Requirements: 17.5_

  - [x] 10.4 Write property test for structured request log
    - **Property 14: Structured Request Log**
    - **Validates: Requirements 17.5**
    - File: `tests/middleware/test_request_log.py`. Hypothesis strategy: random `(method, path, status, duration_ms, user_id)` tuples. Send synthetic requests through the middleware, capture log output, assert exactly one valid JSON line with all fields, correct types, ranges, and `user_id_hash` empty iff unauthenticated.

  - [x] 10.5 Implement Prometheus metrics endpoint
    - Add `app/api/metrics.py` using `prometheus-fastapi-instrumentator` to expose `/metrics` with the counters and histograms named in design C13 (`http_requests_total`, `http_request_duration_seconds`, `langgraph_upstream_failures_total{kind}`, `langgraph_circuit_state`). Update `langgraph_circuit_state` synchronously on every breaker transition.
    - _Requirements: 17.6_

- [ ] 11. Checkpoint - backend client, hardening, and observability
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Implement docker-compose supervisor and host watchdog
  - [x] 12.1 Author production `docker-compose.yml` at the repository root
    - Declare services `admin_backend`, `admin_frontend`, `lightrag_uit`, `postgres_uit`, `qdrant_uit`. For each application service, set `restart: unless-stopped`, `logging: { driver: json-file, options: { max-size: "20m", max-file: "5" } }`, and `stop_grace_period: 30s`.
    - Add a healthcheck for `admin_backend`: `curl -fsS http://localhost:8001/healthz`, `interval: 15s`, `timeout: 3s`, `retries: 3`, `start_period: 30s`.
    - Add a healthcheck for `admin_frontend`: `curl -fsS http://localhost/`, with the same cadence.
    - Inject runtime env via `env_file: /opt/uit/.env`.
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7, 17.1, 17.3_

  - [x] 12.2 Author development overlay `web/apps/admin-dashboard/docker-compose.yml`
    - Add bind mounts for `web/apps/admin-dashboard/{frontend,backend}` and dev-specific env files; keep `restart: unless-stopped` for parity.
    - _Requirements: 16.1, 16.2_

  - [x] 12.3 Implement host-side restart-loop watchdog
    - Add `scripts/supervisor_watchdog.sh` that inspects `docker events` over a rolling 60-second window per service. When a service has restarted ≥5 times in that window, run `docker compose stop <service>`, sleep `min(120, 10 * 2^(n-5))` seconds, then `docker compose start <service>`.
    - Add `deploy/systemd/uit-supervisor-watchdog.timer` and `.service` units that run the watchdog every 30 seconds.
    - _Requirements: 16.5, 16.8_

  - [x] 12.4 Write property test for watchdog backoff
    - **Property 16: Supervisor Restart-Loop Backoff**
    - **Validates: Requirements 16.8**
    - File: `tests/scripts/test_watchdog_backoff.py`. Hypothesis strategy: random sequences of restart event timestamps. Drive a Python harness that mirrors the bash backoff function, assert next-delay equals `min(120, 10 * 2^(n-5))` once `n ≥ 5` and zero otherwise.

  - [x] 12.5 Implement systemd boot unit
    - Add `deploy/systemd/uit-admin-dashboard.service` that runs `docker compose -f /opt/uit/docker-compose.yml up -d` at `multi-user.target` with `TimeoutStopSec=45s`. Document installation steps in the runbook.
    - _Requirements: 17.2_

- [ ] 13. Implement deploy scripts, staging, and production workflows
  - [x] 13.1 Implement `scripts/deploy/ssh_deploy.sh`
    - Accept env vars `SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY_PATH`, `IMAGE_TAG`, `COMPOSE_FILE_PATH`. Write `IMAGE_TAG` to `/opt/uit/.env` over SSH (chmod 600), run `docker compose pull`, `docker compose up -d`, and finally write `/etc/uit-docs/deployment.json` (D3) with the new and previous image tags and Alembic revisions only on success. Bail with a non-zero exit and a `Structured_Error` line on any step failure.
    - _Requirements: 9.2, 9.3, 10.5, 10.6, 13.4_

  - [x] 13.2 Implement `scripts/deploy/rollback.sh`
    - Read `/etc/uit-docs/deployment.json`; restore `previous_image_tag` and `previous_alembic_revision`. Run `docker compose pull` then `docker compose up -d` with the prior tag, then `alembic downgrade <previous_revision>`. Halt the rollback and exit non-zero with a `Structured_Error` if any step fails or the downgrade fails.
    - _Requirements: 9.5, 11.5, 12.6, 12.8_

  - [-] 13.3 Author `staging-deploy.yml`
    - Trigger: `workflow_run: docker-build-publish, types: [completed], branches: [main]` with `if: github.event.workflow_run.conclusion == 'success'`.
    - Concurrency group: `staging-deploy`.
    - Run Vercel preview deploy of `Admin_Frontend` using `${{ secrets.VERCEL_TOKEN }}` and SSH-based deploy of `Admin_Backend` and `LightRAG_Service` using `${{ secrets.STAGING_SSH_HOST }}`, `${{ secrets.STAGING_SSH_USER }}`, `${{ secrets.SSH_PRIVATE_KEY }}` in parallel. Use `continue-on-error: true` per branch so the smoke step runs regardless of single-component failure.
    - Run `scripts/smoke_test.sh` with per-URL timeout 30s and overall budget 5 minutes.
    - On smoke failure, invoke `scripts/deploy/rollback.sh` for staging within 10 minutes and mark the workflow failed.
    - On any failed conclusion, post to the `${{ secrets.DEPLOY_FAILURE_WEBHOOK_URL }}` within 2 minutes naming the failing component, stage, and run URL.
    - Set `timeout-minutes: 15` for the deploy step.
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [-] 13.4 Author `production-deploy.yml`
    - Triggers: `push: tags v*` and `workflow_dispatch` with required string input `image_tag` (1–128 chars).
    - Concurrency group: `production-deploy`.
    - Use the GitHub Environment `production` with manual approval and a 24-hour `wait-timer`/timeout. Mark the run failed if approval is not granted in time.
    - Pre-deploy duplicate-tag guard: read `/etc/uit-docs/deployment.json` over SSH and refuse if `image_tag` equals the currently deployed tag.
    - Deploy steps: `timeout 600 alembic upgrade head` over SSH; `docker compose pull` then `docker compose up -d admin_backend lightrag_uit`; poll `/healthz` on backend and lightrag for ≤60s; on success, run Vercel production deploy/promote with `${{ secrets.VERCEL_TOKEN }}`; run `scripts/smoke_test.sh` with overall budget 30s; write the new `deployment.json`; post a `gh api deployments` status referencing the deployed image tag and run URL.
    - On any failure, run `scripts/deploy/rollback.sh` (skipping Vercel promotion if backend health failed within 60s; rolling back all three within 300s on Vercel error or smoke failure) and emit a deploy-failure notification.
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8, 10.9, 11.1, 11.2, 11.3, 11.4, 11.5, 12.5, 12.6, 12.7, 12.8_

  - [ ] 13.5 Write property test for deployment atomicity
    - **Property 2: Deployment Atomicity**
    - **Validates: Requirements 9.5, 10.8, 11.1, 11.2, 11.3, 11.4, 11.5, 12.7, 12.8**
    - File: `tests/cicd/test_deploy_state_machine.py`. Hypothesis strategy: random failure-injection point ∈ `{migrate, backend_up, lightrag_up, backend_health, lightrag_health, vercel, smoke}`. Drive a pure-Python simulator of the deploy state machine that mirrors the workflow logic. Assert the final state is exactly one of `{all_new_success, all_old_failed}` — never a mixed-version state.

- [ ] 14. Implement CI idempotency replay job
  - [ ] 14.1 Author `ci-idempotency.yml` scheduled workflow
    - Trigger: `schedule: '0 5 * * *'` and `workflow_dispatch`. For a small set of canonical commits, replay `frontend-ci`, `backend-ci`, and `langgraph-ci` twice each on the same runner image and lockfiles. Diff the run summaries (conclusion, test names, artifact filenames) and fail the workflow on any mismatch.
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3_

  - [ ] 14.2 Write property test for CI idempotency model
    - **Property 8: CI Idempotency**
    - **Validates: Requirements 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3**
    - File: `tests/cicd/test_ci_idempotency_model.py`. Hypothesis strategy: random `(commit_sha, runner_image, lockfile_hash)` tuples passed through a deterministic CI simulator. Assert two replays with identical inputs produce identical conclusion, test name set with per-test outcome, and artifact filename set; assert any single-input perturbation produces a different observable.

- [ ] 15. Document secrets, runbook, and migration plan
  - [ ] 15.1 Populate `docs/runbooks/admin-dashboard.md`
    - Fill in `Required Secrets` with each name from R13.1, its purpose, and a rotation cadence ≤ 90 days.
    - Fill in `LangGraph Upstream` with current value (Tailscale endpoint), secret name (`LANGGRAPH_UPSTREAM_URL`), migration target classification, and last-update date; list the contract surface `POST /threads`, `POST /threads/{id}/runs`, `GET /health`; document the secret-only swap procedure.
    - Fill in `Rollback` with numbered steps to revert `admin_backend` image tag, revert the Vercel production deployment, and run `alembic downgrade <previous_revision>`.
    - Fill in `On-call` with the `/healthz` URL for backend, the `/` URL for frontend, the `/metrics` URL, and the alert routes for circuit-breaker open events.
    - Fill in `Operator Commands` with the standard `docker compose ps`, `docker compose logs --tail=200 <service>`, `docker compose restart <service>` and their expected success indicators.
    - Fill in `Production Configuration` with the production values of `CORS_ALLOWED_ORIGINS`, `TRUSTED_HOSTS`, and the `Admin_Frontend` production domain.
    - _Requirements: 13.2, 15.1, 15.2, 15.3, 15.4, 15.5, 17.4, 18.5, 18.6, 20.8_

  - [ ] 15.2 Write content-check tests for the runbook
    - File: `tests/cicd/test_runbook_content.py`. Use exact-match assertions to confirm each named section header is present and that each enumerated secret name appears in the `Required Secrets` section.
    - _Requirements: 13.2, 15.1, 17.4, 18.5, 18.6, 20.8_

- [ ] 16. Final wiring, branch protection, and verification
  - [ ] 16.1 Wire branch protection requirements
    - Add `scripts/ci/configure_branch_protection.sh` that calls the GitHub API to require `frontend-ci`, `backend-ci`, and `langgraph-ci` as status checks on the `main` branch. Document the one-time invocation in the runbook.
    - _Requirements: 2.7, 3.4, 4.4, 5.1, 5.2, 5.3, 5.4_

  - [ ] 16.2 Cross-link workflow registry and CI workflows
    - Verify that `tests/cicd/workflow_registry.py` exactly mirrors the eight authored YAML files (path filters, triggers, concurrency groups). Add `tests/cicd/test_workflow_registry_sync.py` that parses each YAML and asserts equality with the registry; fail if any drift exists.
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 5.4_

- [ ] 17. Final checkpoint - all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP. Per the workflow rules, the implementing agent MUST NOT execute starred sub-tasks.
- Each task references the specific requirement clauses it satisfies for traceability.
- Property tests cover every correctness property defined in the design (Properties 1–17, mapping to CP-1 through CP-8 and the additional design properties). Each property test runs at minimum 100 iterations and is annotated with **Property N** and **Validates: Requirements …**.
- Checkpoints (tasks 4, 11, 17) gate the work into three coherent slices: quality gates, backend hardening, and full deployment.
- Implementation languages: Python 3.11 (backend, CI helper scripts), TypeScript/React (frontend), YAML (GitHub Actions), POSIX bash (deploy and watchdog scripts), per the design.
- Open design decisions T9 in the design document (notification channel, cosign mode, watchdog packaging, Vercel team scope, reproducibility tolerance) are reflected here with the design's defaults; any change must be reconciled in `design.md` first.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["2.1", "2.3", "9.1"] },
    { "id": 2, "tasks": ["2.2", "3.1", "3.2", "3.3", "3.4", "3.5", "3.7", "9.2"] },
    { "id": 3, "tasks": ["3.6", "3.8", "8.1", "9.3", "10.1", "10.3", "12.1", "12.2", "12.3"] },
    { "id": 4, "tasks": ["5.1", "5.2", "6.1", "6.6", "8.2", "9.4", "10.2", "10.4", "10.5", "12.4", "12.5", "13.1", "13.2"] },
    { "id": 5, "tasks": ["5.3", "6.2", "6.3", "6.4", "6.7", "6.8", "9.5", "9.7", "9.9", "13.3", "13.4"] },
    { "id": 6, "tasks": ["6.5", "7.1", "9.6", "9.8", "13.5", "14.1", "15.1"] },
    { "id": 7, "tasks": ["14.2", "15.2", "16.1", "16.2"] }
  ]
}
```
