# Requirements Document

## Introduction

This feature establishes a complete CI/CD pipeline and production deployment workflow for the UIT Docs Agent monorepo, covering the admin dashboard frontend (`web/apps/admin-dashboard/frontend`), admin dashboard backend (`web/apps/admin-dashboard/backend`), the LangGraph agent service (`LangGraph/`), and the LightRAG sidecar (`LightRAG/`).

The feature delivers four integrated capabilities:

1. **CI (Continuous Integration)** — Root-level GitHub Actions workflows that run lint, type-check, unit tests, integration tests, end-to-end tests, and build verification on every pull request and merge to `main`.
2. **CD (Continuous Deployment)** — Automated staging deploys on merge to `main` and gated production deploys on tag `v*` or manual dispatch, with health checks and automatic rollback on smoke-test failure.
3. **LangGraph Upstream Stability** — A defined contract between the admin backend and the LangGraph upstream service (initially the Tailscale endpoint `https://jajajou-bro.tail402a6.ts.net`), including timeouts, retries, structured error responses, and health probing.
4. **Local and Server Supervisor** — A single, durable process management strategy that replaces the current ad-hoc `tmp-*.log` workflow and provides auto-restart, log rotation, health checks, start-on-boot, and graceful shutdown.

The current state (per `web/WEB_STATUS_PLAN.md`) is pilot-ready in functionality (frontend build PASS, 89 vitest tests PASS, e2e mock 15 PASS, e2e live 7 PASS, webkit 2 PASS; backend pytest 68 passed, 1 skipped) but production-blocked on domains, HTTPS, secrets, secure cookies, CORS/trusted-host config, observability, and runbooks. This feature closes those gaps.

## Glossary

- **CI_System**: The GitHub Actions installation triggered by repository events that runs lint, build, and test workflows defined under `.github/workflows/` at the repository root.
- **CD_System**: The deployment subsystem composed of GitHub Actions deployment workflows, the Vercel deployment integration for the frontend, and the SSH-based docker-compose deployer for backend services.
- **Frontend_CI_Workflow**: The GitHub Actions workflow `frontend-ci` defined in `.github/workflows/frontend-ci.yml` that lints, type-checks, unit-tests, builds, and Playwright-mock-tests the admin dashboard frontend.
- **Backend_CI_Workflow**: The GitHub Actions workflow `backend-ci` defined in `.github/workflows/backend-ci.yml` that runs ruff, pytest with coverage, and an Alembic migration check for the admin dashboard backend.
- **LangGraph_CI_Workflow**: The GitHub Actions workflow `langgraph-ci` defined in `.github/workflows/langgraph-ci.yml` that runs the test suite under `LangGraph/tests`.
- **E2E_Live_Workflow**: The GitHub Actions workflow `e2e-live` defined in `.github/workflows/e2e-live.yml` that runs Playwright live-mode tests against a deployed backend connected to the LangGraph upstream.
- **Docker_Build_Workflow**: The GitHub Actions workflow `docker-build-publish` defined in `.github/workflows/docker-build-publish.yml` that builds and publishes container images for `admin_backend`, `admin_frontend`, and `lightrag` to GHCR.
- **Release_Workflow**: The GitHub Actions workflow `release` defined in `.github/workflows/release.yml` that creates a GitHub Release for tags matching `v*` and attaches a generated changelog.
- **Staging_Deploy_Workflow**: The GitHub Actions workflow `staging-deploy` defined in `.github/workflows/staging-deploy.yml` that deploys to the staging environment automatically on push to `main`.
- **Production_Deploy_Workflow**: The GitHub Actions workflow `production-deploy` defined in `.github/workflows/production-deploy.yml` that deploys to the production environment when a tag matching `v*` is pushed or when manually dispatched.
- **GHCR**: The GitHub Container Registry hosted at `ghcr.io`, used as the container image registry for this project.
- **Admin_Backend**: The FastAPI service located at `web/apps/admin-dashboard/backend`, packaged as the container image `admin_backend`, listening on port 8001.
- **Admin_Frontend**: The React 19 + Vite application located at `web/apps/admin-dashboard/frontend`, packaged as the container image `admin_frontend` and also deployable to Vercel.
- **LangGraph_Upstream**: The remote LangGraph service that the Admin_Backend calls for agent execution. The initial production URL is `https://jajajou-bro.tail402a6.ts.net`, supplied via the secret `LANGGRAPH_UPSTREAM_URL`.
- **LangGraph_Service**: The LangGraph implementation source code located in the `LangGraph/` directory of this repository.
- **LightRAG_Service**: The retrieval-augmented service deployed alongside Admin_Backend, reachable internally at `http://lightrag_uit:9621`.
- **Tailscale_Endpoint**: The Tailscale-exposed HTTPS URL `https://jajajou-bro.tail402a6.ts.net` used as the temporary LangGraph_Upstream until a managed deployment is available.
- **Smoke_Test**: The post-deployment verification script that issues an authenticated HTTPS request to the deployed Admin_Backend health endpoint, to the Admin_Frontend root, and to the LangGraph_Upstream health probe, and returns success only when all three return an HTTP status code in the range 200-299 within a maximum total elapsed time of 30 seconds.
- **Health_Check_Endpoint**: The HTTP GET endpoint `/healthz` exposed by Admin_Backend that returns HTTP 200 with JSON `{"status": "ok"}` when the circuit breaker is closed, and HTTP 503 with a Structured_Error body when the circuit breaker is open.
- **Upstream_Probe**: The periodic HTTP GET request issued by Admin_Backend to `${LANGGRAPH_UPSTREAM_URL}/health` to determine LangGraph_Upstream availability.
- **Supervisor**: The process manager responsible for running, restarting, and health-checking Admin_Backend, Admin_Frontend, and LightRAG_Service on a target host. The chosen Supervisor implementation for this feature is docker-compose for both development and production.
- **Compose_File**: The docker-compose YAML file used by the Supervisor. The repository contains `docker-compose.yml` at the root and at `web/apps/admin-dashboard/`; this feature treats `docker-compose.yml` at the repository root as the production source of truth.
- **Secret_Store**: The GitHub Actions encrypted secrets store associated with the repository, used to inject configuration values into CI_System and CD_System workflows.
- **Runbook**: The Markdown document `docs/runbooks/admin-dashboard.md` that describes deployment, rollback, and on-call procedures.
- **Rollback_Procedure**: The documented sequence in the Runbook that restores the previously deployed container image tags for Admin_Backend, LightRAG_Service, and Admin_Frontend, and runs `alembic downgrade` to the previously deployed migration revision.
- **Atomic_Deploy**: A deployment outcome in which Admin_Frontend, Admin_Backend, and LightRAG_Service all reflect the new release version, or all reflect the previous release version, at the conclusion of the Production_Deploy_Workflow run.
- **Structured_Error**: A JSON response body containing the fields `code`, `message`, `request_id`, and `timestamp`, where `code` is a stable machine-readable identifier such as `LANGGRAPH_UNAVAILABLE`.
- **Path_Filter**: The GitHub Actions `paths` filter on a workflow trigger that restricts execution to events touching specific directories.
- **PR**: A GitHub pull request targeting the `main` branch.
- **Developer**: A contributor who opens pull requests, merges to `main`, and consumes CI feedback.
- **DevOps_Engineer**: An operator who configures secrets, deploys to staging and production, owns the Runbook, and responds to deployment alerts.
- **Release_Manager**: An operator who creates `v*` tags and approves manual production deployment dispatches.
- **Admin_User**: An end user of the deployed admin dashboard.

## Requirements

### Requirement 1: Repository CI Workflow Layout

**User Story:** As a Developer, I want a root `.github/workflows/` directory with a clear set of workflows, so that contributors and CI run from a single, discoverable location.

#### Acceptance Criteria

1. THE CI_System SHALL define the workflows `frontend-ci`, `backend-ci`, `langgraph-ci`, `e2e-live`, `docker-build-publish`, `release`, `staging-deploy`, and `production-deploy` as valid YAML files with a `.yml` or `.yaml` extension, located directly under `.github/workflows/` at the repository root.
2. THE CI_System SHALL apply a Path_Filter to `frontend-ci` that restricts `pull_request` and `push` triggers to events whose changed file set contains at least one path matching `web/apps/admin-dashboard/frontend/**` or `.github/workflows/frontend-ci.yml`.
3. THE CI_System SHALL apply a Path_Filter to `backend-ci` that restricts `pull_request` and `push` triggers to events whose changed file set contains at least one path matching `web/apps/admin-dashboard/backend/**` or `.github/workflows/backend-ci.yml`.
4. THE CI_System SHALL apply a Path_Filter to `langgraph-ci` that restricts `pull_request` and `push` triggers to events whose changed file set contains at least one path matching `LangGraph/**` or `.github/workflows/langgraph-ci.yml`.
5. WHEN a pull request targeting the `main` branch is opened, reopened, or synchronized with new commits, THE CI_System SHALL trigger every workflow whose Path_Filter matches at least one file in the pull request's changed file set.
6. WHEN a push to the `main` branch occurs, THE CI_System SHALL trigger every workflow whose Path_Filter matches at least one file in the pushed commits' changed file set.
7. IF a pull request or push event's changed file set does not match a workflow's Path_Filter, THEN THE CI_System SHALL NOT trigger that workflow for the event.
8. THE CI_System SHALL configure the `e2e-live`, `docker-build-publish`, `release`, `staging-deploy`, and `production-deploy` workflows with explicit triggers (such as manual dispatch, tag push, or environment-scoped events) that do not depend on the `frontend-ci`, `backend-ci`, or `langgraph-ci` Path_Filters.

### Requirement 2: Frontend CI Quality Gates

**User Story:** As a Developer, I want the frontend pipeline to enforce lint, type, unit, build, and Playwright mock checks, so that broken frontend code cannot be merged.

#### Acceptance Criteria

1. WHEN a pull request targeting `main` is opened, reopened, or synchronized, or a push to `main` occurs that touches `web/apps/admin-dashboard/frontend/**` or `.github/workflows/frontend-ci.yml`, THE CI_System SHALL trigger Frontend_CI_Workflow within 60 seconds of the event.
2. WHEN Frontend_CI_Workflow is triggered, THE CI_System SHALL execute the steps `npm ci`, `npm run lint`, `npm run typecheck`, `npm run test -- --run`, `npm run build`, and `npm run test:e2e:mock` strictly in that order in the working directory `web/apps/admin-dashboard/frontend`, with each step starting only after the previous step has exited with status 0.
3. IF any step in Frontend_CI_Workflow exits with a non-zero status, THEN THE CI_System SHALL halt subsequent steps and mark the workflow run conclusion as `failure`.
4. THE CI_System SHALL distinguish runner-level cancellations and infrastructure errors from step failures, marking the workflow run conclusion as `cancelled` rather than `failure` when no step has produced a non-zero exit status.
5. WHEN the `npm run build` step in Frontend_CI_Workflow exits with status 0, THE CI_System SHALL upload the contents of `web/apps/admin-dashboard/frontend/dist` as an artifact named `admin-frontend-dist-${{ github.sha }}` with a retention of 14 days.
6. WHEN the `npm run test -- --run` step in Frontend_CI_Workflow exits with status 0, THE CI_System SHALL upload the coverage report as an artifact named `admin-frontend-coverage-${{ github.sha }}` with a retention of 14 days.
7. THE CI_System SHALL configure GitHub branch protection on `main` to require Frontend_CI_Workflow conclusion `success` before a PR can be merged.

### Requirement 3: Backend CI Quality Gates

**User Story:** As a Developer, I want the backend pipeline to enforce lint, tests with coverage, and Alembic migration verification, so that backend regressions and broken migrations cannot reach `main`.

#### Acceptance Criteria

1. WHEN a pull request targeting `main` is opened, reopened, or synchronized, or a push to `main` occurs that touches `web/apps/admin-dashboard/backend/**` or `.github/workflows/backend-ci.yml`, THE CI_System SHALL trigger Backend_CI_Workflow and execute, in order, the steps install Python 3.11, install dependencies from `web/apps/admin-dashboard/backend/requirements.txt` and `requirements-dev.txt`, run `ruff check .`, run `pytest --cov=app --cov-report=xml`, and run the Alembic migration check defined in Requirement 12, all from the working directory `web/apps/admin-dashboard/backend`.
2. IF any step in Backend_CI_Workflow exits with a non-zero status, THEN THE CI_System SHALL mark the workflow run as failed and SHALL skip every subsequent step except the artifact upload step in Acceptance Criterion 3.
3. WHEN Backend_CI_Workflow reaches the artifact upload step, THE CI_System SHALL upload `coverage.xml` (when present) as an artifact named `admin-backend-coverage-${{ github.sha }}` with a retention of 14 days, regardless of pytest exit status.
4. THE CI_System SHALL configure GitHub branch protection on `main` to require Backend_CI_Workflow to report a `success` status check before a PR can be merged.
5. WHERE the file `web/apps/admin-dashboard/backend/mypy.ini` or `web/apps/admin-dashboard/backend/pyproject.toml` declares mypy configuration, THE Backend_CI_Workflow SHALL run `mypy app` immediately after `ruff check .` and before `pytest`.
6. WHEN the `pytest` step completes with exit status 0, THE Backend_CI_Workflow SHALL fail the run if line coverage as reported in `coverage.xml` is below 70 percent.
7. THE Backend_CI_Workflow run SHALL terminate with a non-zero conclusion if total wall-clock execution exceeds 20 minutes.

### Requirement 4: LangGraph CI Workflow

**User Story:** As a Developer, I want LangGraph changes to run their unit and integration tests on every PR, so that agent regressions surface before merge.

#### Acceptance Criteria

1. WHEN a pull request targeting `main` is opened, synchronized, or reopened, THE CI_System SHALL trigger LangGraph_CI_Workflow and execute the test suites declared in `LangGraph/.github/workflows/unit-tests.yml` and `LangGraph/.github/workflows/integration-tests.yml` using a `workflow_call` or equivalent reuse mechanism, with the entire run completing within 30 minutes.
2. WHERE the `workflow_call` reuse mechanism is unavailable, THE CI_System SHALL run `pytest LangGraph/tests` from the repository root using the Python version declared in those internal workflows.
3. IF the LangGraph test suite exits with a non-zero status or its execution exceeds 30 minutes, THEN THE CI_System SHALL mark LangGraph_CI_Workflow as failed and report the failed status to the originating pull request.
4. THE CI_System SHALL configure GitHub branch protection on `main` to require LangGraph_CI_Workflow to pass as a required status check before a pull request can be merged.

### Requirement 5: Parallel Execution and Merge Blocking

**User Story:** As a Developer, I want CI workflows to run in parallel and to block merging on failure, so that feedback is fast and `main` stays green.

#### Acceptance Criteria

1. WHEN multiple workflows are triggered by the same PR event, THE CI_System SHALL start all triggered workflows in parallel within 30 seconds of the event being received and SHALL NOT serialize their execution.
2. IF any required workflow run associated with a PR concludes with status `failure` or `cancelled`, THEN THE CI_System SHALL disable the merge action on the PR, display a failed-check indicator on every required check, and SHALL re-enable the merge action only when the failed required check has been re-run with conclusion `success` or has been superseded by a new commit on the PR's head branch.
3. WHILE a required workflow run associated with a PR is in progress and has not yet concluded, THE CI_System SHALL allow the PR to be merged when GitHub branch protection settings permit auto-merge with pending checks, and otherwise SHALL block the merge until every required check has concluded with status `success`.
4. WHEN a PR's commit set changes, THE CI_System SHALL cancel any in-progress runs of the same workflow on prior commits of the same PR within 60 seconds using a concurrency group keyed by the workflow identifier and the PR's reference (corresponding to `${{ github.workflow }}-${{ github.ref }}` in GitHub Actions).

### Requirement 6: Live End-to-End Testing Against LangGraph Upstream

**User Story:** As a DevOps_Engineer, I want a scheduled live E2E run against the deployed backend and LangGraph_Upstream, so that integration drift is detected daily.

#### Acceptance Criteria

1. THE E2E_Live_Workflow SHALL be triggered on a `schedule` cron of `0 18 * * *` (daily 18:00 UTC) and on `workflow_dispatch`, with a concurrency group keyed by the workflow name that cancels any prior in-progress run.
2. WHEN E2E_Live_Workflow runs, THE CI_System SHALL inject the secret `LANGGRAPH_UPSTREAM_URL` as the environment variable `LANGGRAPH_UPSTREAM_URL` into the Playwright run.
3. IF the secret `LANGGRAPH_UPSTREAM_URL` is unset or empty when E2E_Live_Workflow starts, THEN THE E2E_Live_Workflow SHALL mark the run as failed with the annotation `LANGGRAPH_UPSTREAM_URL secret missing` and SHALL NOT execute the Upstream_Probe or Playwright steps.
4. WHEN E2E_Live_Workflow starts and the secret `LANGGRAPH_UPSTREAM_URL` is non-empty, THE CI_System SHALL issue a single HTTP GET Upstream_Probe to `${LANGGRAPH_UPSTREAM_URL}/health` with a 5-second combined connect-and-response timeout before running Playwright.
5. IF the Upstream_Probe returns a non-2xx status or fails to respond within 5 seconds, THEN THE E2E_Live_Workflow SHALL mark the Playwright job as skipped with the annotation `LangGraph upstream unavailable` and SHALL exit with status 0.
6. WHEN the Upstream_Probe returns a 2xx status, THE E2E_Live_Workflow SHALL execute the Playwright live configuration `playwright.live.config.ts` with a maximum execution time of 30 minutes, and SHALL upload the resulting `playwright-report` directory as an artifact with 14-day retention regardless of test outcome.
7. IF the Playwright run exits with a non-zero status or exceeds the 30-minute maximum execution time, THEN THE E2E_Live_Workflow SHALL mark the run as failed and SHALL distinguish this conclusion from the `LangGraph upstream unavailable` skip path.

### Requirement 7: Container Image Build and Publish

**User Story:** As a DevOps_Engineer, I want signed, tagged container images published to GHCR on every merge and release, so that deployments pull immutable, traceable artifacts.

#### Acceptance Criteria

1. WHEN a commit is pushed to the `main` branch and the workflow trigger fires, THE Docker_Build_Workflow SHALL build the images `ghcr.io/<owner>/admin_backend`, `ghcr.io/<owner>/admin_frontend`, and `ghcr.io/<owner>/lightrag`, and upon successful build of each image SHALL push it to GHCR with the tags `main` and `sha-${{ github.sha }}`, completing all build and push operations within 30 minutes per image.
2. WHEN a tag matching the pattern `v*` is pushed to the repository, THE Docker_Build_Workflow SHALL build the images `ghcr.io/<owner>/admin_backend`, `ghcr.io/<owner>/admin_frontend`, and `ghcr.io/<owner>/lightrag`, and upon successful build of each image SHALL push it to GHCR with the tags `${{ github.ref_name }}` and `latest`, completing all build and push operations within 30 minutes per image.
3. WHEN the Docker_Build_Workflow begins a build job, THE Docker_Build_Workflow SHALL authenticate to GHCR using the `GITHUB_TOKEN` with `packages: write` permission before initiating any push operation.
4. WHEN Docker_Build_Workflow builds an image, THE CI_System SHALL pass the build arguments `GIT_SHA=${{ github.sha }}` and `BUILD_TIME` (formatted as an ISO 8601 UTC timestamp with second precision, e.g., `2025-01-15T12:34:56Z`) to the Docker build context.
5. THE Docker_Build_Workflow SHALL produce build outputs that are byte-identical between two runs of the same commit on the same builder image, given identical build arguments and lockfiles, as defined in Requirement 19.
6. WHEN Docker_Build_Workflow successfully pushes an image to GHCR, THE Docker_Build_Workflow SHALL generate and publish a cryptographic signature bound to that image's digest to GHCR before the workflow run is marked successful.
7. IF any image build or push step in Docker_Build_Workflow fails, THEN THE Docker_Build_Workflow SHALL halt subsequent push and signing operations for the failing image, mark the workflow run as failed with an error indication identifying the failed image and step, and SHALL NOT publish partially built or unsigned artifacts to GHCR.
8. IF authentication to GHCR using `GITHUB_TOKEN` fails, THEN THE Docker_Build_Workflow SHALL retry authentication at most 2 additional times within the same workflow run, and on continued failure SHALL abort all push operations and mark the workflow run as failed with an error indication identifying authentication failure.

### Requirement 8: GitHub Release Generation

**User Story:** As a Release_Manager, I want a GitHub Release auto-created from a `v*` tag with a changelog, so that consumers can identify what shipped.

#### Acceptance Criteria

1. WHEN a tag matching the pattern `v<MAJOR>.<MINOR>.<PATCH>` (with an optional `-<pre-release>` suffix) is pushed, THE Release_Workflow SHALL create a GitHub Release whose name and tag both equal the pushed tag, within 120 seconds of the push event.
2. IF the Release_Workflow fails to create the GitHub Release due to API errors or insufficient permissions, THEN THE CI_System SHALL mark the Release_Workflow run as failed with a visible error indication identifying the failure cause.
3. IF the Release_Workflow run is marked as failed per Acceptance Criterion 2, THEN THE CI_System SHALL leave the underlying tag in place and SHALL NOT retry release creation automatically.
4. WHEN Release_Workflow runs and a previous tag matching the same pattern exists in the repository, THE CI_System SHALL include in the release body a changelog section generated from the commit messages between the previous matching tag and the new tag using the GitHub-native release-notes generation API.
5. WHEN Release_Workflow runs and no previous tag matching the same pattern exists in the repository, THE CI_System SHALL include in the release body a changelog section generated from all commits reachable from the new tag using the GitHub-native release-notes generation API.
6. WHEN Release_Workflow runs, THE CI_System SHALL include in the release body a distinct section listing the published image references `ghcr.io/<owner>/admin_backend:<tag>`, `ghcr.io/<owner>/admin_frontend:<tag>`, and `ghcr.io/<owner>/lightrag:<tag>`.

### Requirement 9: Staging Deployment

**User Story:** As a DevOps_Engineer, I want every merge to `main` to deploy automatically to staging, so that the team always has a current preview environment.

#### Acceptance Criteria

1. WHEN Docker_Build_Workflow concludes with a success status on a push to `main`, THE Staging_Deploy_Workflow SHALL be triggered via `workflow_run` within 60 seconds.
2. WHEN Staging_Deploy_Workflow runs, THE CD_System SHALL deploy Admin_Frontend to a Vercel preview deployment using the secret `VERCEL_TOKEN` and SHALL deploy Admin_Backend and LightRAG_Service to the staging host using the secrets `STAGING_SSH_HOST`, `STAGING_SSH_USER`, and `SSH_PRIVATE_KEY` by running `docker compose pull` followed by `docker compose up -d` against the staging Compose_File, completing all deploy steps within 15 minutes total.
3. IF deployment of any single component (Admin_Frontend, Admin_Backend, or LightRAG_Service) exits with a non-zero status or exceeds the 15-minute deployment timeout, THEN THE CD_System SHALL continue deploying the remaining components and SHALL rely on the Smoke_Test step to detect resulting health failures.
4. WHEN Staging_Deploy_Workflow finishes the deploy step, THE CD_System SHALL run the Smoke_Test against the staging URLs with a per-URL timeout of 30 seconds and an overall budget of 5 minutes, where each URL passes when it returns a successful health response and fails on timeout, connection failure, or unsuccessful response.
5. IF the Smoke_Test reports any URL as failed, THEN THE Staging_Deploy_Workflow SHALL execute the Rollback_Procedure for the staging environment by redeploying the previously known-good deployment state via `docker compose up -d` within 10 minutes, and SHALL mark the workflow run as failed.
6. WHEN Staging_Deploy_Workflow concludes with a failed status, THE CD_System SHALL emit a failure notification to the DevOps_Engineer within 2 minutes that names the failing component, the stage that produced the failure, and a reference to the workflow run.

### Requirement 10: Production Deployment

**User Story:** As a Release_Manager, I want production deploys to be gated by either a `v*` tag or manual dispatch and to auto-rollback on smoke-test failure, so that production stays stable.

#### Acceptance Criteria

1. THE Production_Deploy_Workflow SHALL be triggered on `push` of tags matching `v*` and on `workflow_dispatch` with a required input `image_tag` of type `string` between 1 and 128 characters.
2. IF Production_Deploy_Workflow is triggered by `workflow_dispatch` with an `image_tag` value that equals the image tag currently deployed in production, THEN THE CD_System SHALL refuse the run with a failure message identifying the duplicate image tag and SHALL NOT execute the deploy job.
3. WHEN Production_Deploy_Workflow is triggered by `workflow_dispatch`, THE CD_System SHALL require the GitHub Environment `production` to provide manual approval within 24 hours before the deploy job runs.
4. IF the manual approval for the GitHub Environment `production` is not granted within 24 hours of the `workflow_dispatch` trigger, THEN THE CD_System SHALL mark the workflow run as failed and SHALL NOT execute the deploy job.
5. WHEN Production_Deploy_Workflow runs the deploy job, THE CD_System SHALL deploy Admin_Frontend to the Vercel production deployment using the secret `VERCEL_TOKEN`.
6. WHEN Production_Deploy_Workflow runs the deploy job, THE CD_System SHALL deploy Admin_Backend and LightRAG_Service to the production host using the secrets `PROD_SSH_HOST`, `PROD_SSH_USER`, and `SSH_PRIVATE_KEY` by running `docker compose pull` followed by `docker compose up -d` against the production Compose_File.
7. WHEN Production_Deploy_Workflow finishes the deploy step, THE CD_System SHALL run the Smoke_Test against the production URLs with a maximum duration of 30 seconds.
8. IF the Smoke_Test returns a non-success result or does not complete within 30 seconds, THEN THE Production_Deploy_Workflow SHALL execute the Rollback_Procedure to restore the previously deployed image tag in production and SHALL mark the workflow run as failed.
9. WHEN Production_Deploy_Workflow completes successfully, THE CD_System SHALL post a deployment status update to GitHub Deployments referencing the deployed image tag and the run URL.

### Requirement 11: Atomic Deployment Across Frontend and Backend

**User Story:** As a DevOps_Engineer, I want frontend and backend deploys to succeed or roll back together, so that production never serves a mismatched pair.

#### Acceptance Criteria

1. WHEN Production_Deploy_Workflow runs, THE CD_System SHALL complete deployment of Admin_Backend and LightRAG_Service and verify each returns HTTP 200 from its Health_Check_Endpoint before promoting the Vercel production deployment for Admin_Frontend.
2. IF the Health_Check_Endpoint of Admin_Backend or LightRAG_Service does not return HTTP 200 within 60 seconds of the post-deploy probe starting, THEN THE Production_Deploy_Workflow SHALL skip the Vercel promotion step and SHALL execute the Rollback_Procedure for every component deployed in the current run.
3. IF the Vercel promotion step returns an error status, THEN THE Production_Deploy_Workflow SHALL execute the Rollback_Procedure for Admin_Backend, LightRAG_Service, and Admin_Frontend within 300 seconds of the error being detected.
4. THE deployment outcome of every Production_Deploy_Workflow run SHALL satisfy the Atomic_Deploy definition such that Admin_Frontend, Admin_Backend, and LightRAG_Service all reflect the new release version or all reflect the previous release version at run completion.
5. IF the Rollback_Procedure fails to restore any component to its previous release version within 300 seconds, THEN THE Production_Deploy_Workflow SHALL terminate with a failed status and SHALL emit a deploy failure notification identifying the affected component.

### Requirement 12: Alembic Migration Safety

**User Story:** As a Developer, I want every migration to be reversible and verified in CI, so that production rollbacks remain possible.

#### Acceptance Criteria

1. WHEN Backend_CI_Workflow runs the Alembic migration check, THE CI_System SHALL execute, against an ephemeral SQLite database stored in a temporary file that is deleted after the check completes, the sequence `alembic upgrade head` followed by `alembic downgrade base` followed by `alembic upgrade head`, all from the directory `web/apps/admin-dashboard/backend`, with each command bounded by a 300-second timeout.
2. IF any of the Alembic commands in the migration check exits with a non-zero status or exceeds its 300-second timeout, THEN THE Backend_CI_Workflow SHALL mark the run as failed with a non-zero workflow exit.
3. THE Backend_CI_Workflow SHALL fail the Alembic migration check only when an `alembic` command exits with a non-zero status or exceeds its 300-second timeout, and SHALL NOT introduce additional failure conditions for missing migration files or database connection issues beyond what `alembic` itself reports through its exit code.
4. THE CI_System SHALL verify that the workflow conclusion matches the exit codes of the Alembic commands by reading the recorded step exit codes and SHALL fail the workflow if any step exit code is non-zero even when the workflow runner reports success for the step.
5. WHEN Production_Deploy_Workflow runs and the deployed image contains a new Alembic revision, THE CD_System SHALL run `alembic upgrade head` before starting the new Admin_Backend container and SHALL wait at most 600 seconds for the command to complete.
6. WHEN the Rollback_Procedure runs after a failed deploy that included a new Alembic revision, THE CD_System SHALL run `alembic downgrade <previous_revision>` against the production database, where `<previous_revision>` is the Alembic revision recorded by the most recent successful Production_Deploy_Workflow run.
7. IF `alembic upgrade head` during Production_Deploy_Workflow exits with a non-zero status or exceeds 600 seconds, THEN THE CD_System SHALL abort the deploy, retain the previously running Admin_Backend container, and mark the workflow run as failed.
8. IF `alembic downgrade` during Rollback_Procedure exits with a non-zero status, THEN THE CD_System SHALL halt the rollback, retain the current database state, and mark the workflow run as failed with a notification identifying the failed downgrade revision.

### Requirement 13: Secret Management

**User Story:** As a DevOps_Engineer, I want every required secret declared in one place and never written to logs or images, so that credentials cannot leak.

#### Acceptance Criteria

1. THE CI_System SHALL read the secrets `VERCEL_TOKEN`, `SSH_PRIVATE_KEY`, `STAGING_SSH_HOST`, `STAGING_SSH_USER`, `PROD_SSH_HOST`, `PROD_SSH_USER`, `LANGGRAPH_UPSTREAM_URL`, `LIGHTRAG_API_KEY`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `POSTGRES_DSN`, and `JWT_SECRET` exclusively from the Secret_Store.
2. THE Runbook SHALL contain a section named "Required Secrets" that lists every name in Acceptance Criterion 1 with its purpose and a rotation cadence not exceeding 90 days.
3. THE CI_System SHALL set every secret-derived environment variable using the GitHub Actions `secrets` context so that on every line of stdout, stderr, and workflow log output, the secret value is rendered as `***`.
4. IF a workflow step needs to write a secret to disk, THEN the step SHALL write to a file under `${{ runner.temp }}` accessible only to the runner user, and SHALL delete the file in a `post`-step or `if: always()` cleanup step that runs regardless of prior step success or failure.
5. THE Docker_Build_Workflow SHALL pass secrets to image builds only via Docker BuildKit `--secret` mounts and SHALL NOT pass secrets via build arguments, baked environment variables, or files copied into the image.
6. WHEN any container image is published, THE Docker_Build_Workflow SHALL resolve the current values of every secret listed in Acceptance Criterion 1 from the Secret_Store and run a final scan that fails the workflow if any of those resolved values appears in plaintext in the image's file content or any image layer.
7. IF the secret-scan step in Acceptance Criterion 6 fails to execute within 600 seconds (for example because the scanner image cannot be pulled or the scanner crashes), THEN THE Docker_Build_Workflow SHALL fail closed by marking the workflow run as failed and SHALL NOT publish the image.
8. THE Docker_Build_Workflow SHALL only run the secret-scan step in Acceptance Criterion 6 on jobs that push images to a remote container registry, and SHALL NOT run the scan during local-build-cache jobs used for unit, integration, or PR validation.

### Requirement 14: LangGraph Upstream Contract

**User Story:** As an Admin_User, I want the admin backend to remain available even when LangGraph_Upstream is degraded, so that admin operations not requiring the agent continue to work.

#### Acceptance Criteria

1. THE Admin_Backend SHALL read the LangGraph_Upstream base URL exclusively from the environment variable `LANGGRAPH_UPSTREAM_URL` at process startup.
2. WHEN Admin_Backend issues a request to LangGraph_Upstream, THE Admin_Backend SHALL apply a connect timeout of 5 seconds and a read timeout of 30 seconds.
3. IF a request to LangGraph_Upstream fails with a connection error, a request timeout, or a 5xx response, THEN THE Admin_Backend SHALL retry the request up to 2 additional times using exponential backoff starting at 500 ms and capped at 4 seconds per retry delay, and SHALL NOT retry on 4xx responses.
4. WHILE the count of LangGraph_Upstream call failures (counted as connection errors, request timeouts, or 5xx responses after retries are exhausted) is greater than or equal to 5 within a rolling 60-second window, THE Admin_Backend SHALL open a circuit breaker that returns HTTP 503 with Structured_Error code `LANGGRAPH_UNAVAILABLE` for any new LangGraph-dependent endpoint without issuing the upstream request.
5. WHILE the circuit breaker is open, THE Admin_Backend SHALL probe LangGraph_Upstream every 30 seconds and SHALL close the circuit after 2 consecutive probes that return an HTTP 2xx response within the connect and read timeouts.
6. IF LangGraph_Upstream returns a non-2xx response or the timeout elapses, THEN THE Admin_Backend SHALL log a Structured_Error entry containing `code=LANGGRAPH_UNAVAILABLE`, the upstream URL with credentials redacted, the elapsed time in milliseconds, and the request id, and SHALL NOT propagate the raw upstream response body to the Admin_User regardless of whether the structured log entry was successfully written.
7. THE Admin_Backend SHALL expose the Health_Check_Endpoint, and the endpoint SHALL return HTTP 200 whenever the circuit breaker is closed, regardless of the most recent observed reachability of LangGraph_Upstream, and SHALL return HTTP 503 with Structured_Error code `LANGGRAPH_UNAVAILABLE` whenever the circuit breaker is open.
8. IF the environment variable `LANGGRAPH_UPSTREAM_URL` is unset, empty, or not a syntactically valid http or https URL at process startup, THEN THE Admin_Backend SHALL terminate startup and SHALL emit a Structured_Error entry with code `LANGGRAPH_UPSTREAM_URL_MISSING`.
9. IF all retry attempts for a LangGraph_Upstream request are exhausted without a 2xx response, THEN THE Admin_Backend SHALL return HTTP 503 with Structured_Error code `LANGGRAPH_UNAVAILABLE` to the calling Admin_User without exposing the upstream response body.

### Requirement 15: LangGraph Upstream Migration Plan

**User Story:** As a DevOps_Engineer, I want the temporary Tailscale upstream documented and a migration path defined, so that we can replace it without code changes.

#### Acceptance Criteria

1. THE Runbook SHALL contain a section named "LangGraph Upstream" that records, as discrete fields, the current value (Tailscale_Endpoint), the secret name (`LANGGRAPH_UPSTREAM_URL`), the migration target classification (managed or self-hosted LangGraph deployment), and the date of last update.
2. WHEN the LangGraph_Upstream URL changes, THE DevOps_Engineer SHALL update only the secret `LANGGRAPH_UPSTREAM_URL` and the Runbook entry, and SHALL NOT modify Admin_Backend source code, container images, or build artifacts.
3. THE Runbook SHALL list the contract surface that the migration target must implement: a `POST /threads`, a `POST /threads/{id}/runs`, and a `GET /health` endpoint, where contract conformance is verified by the existing Admin_Backend client functioning without changes against the migration target.
4. WHEN the LangGraph_Upstream URL is changed to a migration target, THE DevOps_Engineer SHALL execute and record the outcome of a `GET /health` probe and a `POST /threads` smoke test against the migration target before promoting it as the live upstream.
5. IF the post-migration probe or smoke test in Acceptance Criterion 4 returns a non-2xx response, THEN THE DevOps_Engineer SHALL revert the secret `LANGGRAPH_UPSTREAM_URL` to the previously known-good value within 15 minutes without modifying Admin_Backend source code, container images, or build artifacts.

### Requirement 16: Supervisor Choice and Behavior

**User Story:** As a DevOps_Engineer, I want a single, declared process supervisor that replaces the ad-hoc `tmp-*.log` workflow, so that local and server runs behave consistently.

#### Acceptance Criteria

1. THE Supervisor for development and production SHALL be docker-compose, using the Compose_File `docker-compose.yml` at the repository root as the production source of truth and `web/apps/admin-dashboard/docker-compose.yml` as the development overlay.
2. THE Compose_File SHALL declare the services `admin_backend`, `admin_frontend`, and `lightrag_uit`, each with `restart: unless-stopped`.
3. THE Compose_File SHALL declare a Docker `healthcheck` for `admin_backend` that issues `curl -fsS http://localhost:8001/healthz` every 15 seconds with a 3-second timeout, 3 retries, and a 30-second `start_period`.
4. THE Compose_File SHALL declare a Docker `healthcheck` for `admin_frontend` that issues `curl -fsS http://localhost/` every 15 seconds with a 3-second timeout, 3 retries, and a 30-second `start_period`.
5. IF the Supervisor reports that any service has exited with a non-zero status or has transitioned to the `unhealthy` state, THEN THE Supervisor SHALL restart that service within 10 seconds of the event timestamp.
6. WHEN the production host receives a SIGTERM for the Supervisor, THE Supervisor SHALL forward SIGTERM to all managed containers within 1 second.
7. IF a managed container has not exited 30 seconds after the Supervisor forwarded SIGTERM, THEN THE Supervisor SHALL issue SIGKILL to that container.
8. WHILE a service has been restarted 5 or more times within a rolling 60-second window, THE Supervisor SHALL apply exponential backoff starting at 10 seconds and capped at 120 seconds before the next restart attempt.

### Requirement 17: Log Rotation, Boot, and Observability

**User Story:** As a DevOps_Engineer, I want logs rotated, services to start on boot, and a documented observability surface, so that we are not blind in production.

#### Acceptance Criteria

1. THE Compose_File SHALL configure the `json-file` Docker logging driver for every defined service with `max-size=20m` and `max-file=5`.
2. THE production host SHALL enable the Docker daemon's systemd unit so that the Supervisor and its services start automatically within 180 seconds of host boot completion.
3. THE Compose_File SHALL declare `restart: unless-stopped` for every defined service so that services restart on crash and on host reboot.
4. THE Runbook SHALL document the host-side commands `docker compose ps`, `docker compose logs --tail=200 <service>`, and `docker compose restart <service>` as the standard operator commands, including the expected success indicators for each command.
5. WHEN Admin_Backend handles an HTTP request, THE Admin_Backend SHALL emit exactly one structured log line containing the fields `timestamp` (UTC ISO 8601), `request_id` (non-empty string), `method`, `path`, `status` (integer), `duration_ms` (integer in the range 0 to 600000), and `user_id_hash` (empty when the request is unauthenticated).
6. THE Admin_Backend SHALL expose Prometheus metrics at `/metrics`, including the counter `http_requests_total`, the histogram `http_request_duration_seconds`, the counter `langgraph_upstream_failures_total`, and the gauge `langgraph_circuit_state`, with the endpoint responding within 2 seconds.

### Requirement 18: Smoke Test Definition and Runbook

**User Story:** As a DevOps_Engineer, I want a single smoke-test script and a written runbook, so that staging and production deploys verify the same surface and operators know how to recover.

#### Acceptance Criteria

1. THE repository SHALL contain the script `scripts/smoke_test.sh` that requires the arguments `--frontend-url`, `--backend-url`, and `--upstream-url`, and exits with status 0 only when all three URLs return an HTTP status code in the range 200 to 299 within a maximum total elapsed time of 30 seconds.
2. WHEN the Smoke_Test runs with all three required arguments supplied, THE script SHALL issue HTTP GET requests to the Health_Check_Endpoint at `${backend-url}/healthz`, the path `/` at `${frontend-url}`, and the path `/health` at `${upstream-url}`.
3. IF any single request returns an HTTP status code outside the range 200 to 299 or exceeds a per-request timeout of 5 seconds, THEN THE script SHALL exit with status 1 and SHALL print a Structured_Error to stdout identifying the failed URL, the observed status code (or the sentinel `timeout` when the per-request timeout is exceeded), and the elapsed time in milliseconds.
4. IF the script encounters a DNS resolution error, a TLS handshake failure, a missing required argument, or an unrecognized argument, THEN THE script SHALL exit with status 1 and SHALL print a Structured_Error to stdout in the same shape defined in Acceptance Criterion 3.
5. THE Runbook SHALL contain a section named "Rollback" that documents, in numbered steps, how to revert the Admin_Backend image tag, revert the Admin_Frontend Vercel deployment, and run `alembic downgrade <previous_revision>`.
6. THE Runbook SHALL contain a section named "On-call" that lists the Health_Check_Endpoint URL for Admin_Backend, the Health_Check_Endpoint URL for Admin_Frontend, the Prometheus metrics endpoint, and the alert routes for circuit-breaker open events.

### Requirement 19: Build Reproducibility

**User Story:** As a Developer, I want repeated CI runs of the same commit to produce identical artifacts, so that we can trust image provenance and diagnose regressions.

#### Acceptance Criteria

1. WHEN Docker_Build_Workflow builds an image from the same commit SHA twice on the same builder image version and the same lockfiles, THE Docker_Build_Workflow SHALL produce two image manifests whose layer digests for the layers containing application source code and installed dependencies are byte-for-byte identical.
2. WHEN Frontend_CI_Workflow installs frontend dependencies, THE Frontend_CI_Workflow SHALL execute `npm ci` so that dependency resolution uses `package-lock.json` exclusively and does not modify the lockfile.
3. WHEN Backend_CI_Workflow installs Python dependencies, THE Backend_CI_Workflow SHALL install from `requirements.txt` where every package entry specifies an exact version pin using `==`.
4. WHEN Docker_Build_Workflow builds an image, THE Docker_Build_Workflow SHALL set `SOURCE_DATE_EPOCH` to the Unix timestamp of the commit being built before any layer that embeds file modification times is created.
5. IF `requirements.txt` contains any package entry without an exact version pin, THEN THE Backend_CI_Workflow SHALL fail the build before running `pip install` and emit an error message indicating which package entries are unpinned.
6. IF `package-lock.json` is missing or inconsistent with `package.json` when Frontend_CI_Workflow installs dependencies, THEN THE Frontend_CI_Workflow SHALL fail the build and emit an error message indicating the lockfile inconsistency.

### Requirement 20: Production Configuration Hardening

**User Story:** As an Admin_User, I want production traffic served over HTTPS with secure cookies and correctly scoped CORS, so that my session cannot be hijacked.

#### Acceptance Criteria

1. WHILE the Admin_Frontend is deployed to the production environment, THE Admin_Frontend SHALL be served only over HTTPS.
2. IF an HTTP request is received for the Admin_Frontend production domain, THEN the Vercel project SHALL redirect the client to the equivalent HTTPS URL with a permanent redirect status.
3. WHEN the Admin_Backend issues an authentication cookie in the production environment, THE Admin_Backend SHALL set the cookie attributes `Secure`, `HttpOnly`, and `SameSite=Lax` on that cookie.
4. THE Admin_Backend SHALL load the allowed CORS origins exclusively from the environment variable `CORS_ALLOWED_ORIGINS` at startup, and IF an incoming request has an `Origin` header that is not present in that list, THEN THE Admin_Backend SHALL reject the request with HTTP 403.
5. IF the environment variable `CORS_ALLOWED_ORIGINS` is unset, empty, or fails to parse at Admin_Backend startup, THEN THE Admin_Backend SHALL reject every cross-origin request with HTTP 403 and SHALL log a Structured_Error with code `CORS_MISCONFIGURED`.
6. THE Admin_Backend SHALL load the allowed trusted hosts exclusively from the environment variable `TRUSTED_HOSTS` at startup, and IF an incoming request has a `Host` header that is not present in that list, THEN THE Admin_Backend SHALL reject the request with HTTP 400, even when the request's `Origin` header is in `CORS_ALLOWED_ORIGINS`.
7. IF the environment variable `TRUSTED_HOSTS` is unset, empty, or fails to parse at Admin_Backend startup, THEN THE Admin_Backend SHALL reject every incoming request with HTTP 400 and SHALL log a Structured_Error with code `TRUSTED_HOSTS_MISCONFIGURED`.
8. THE Runbook SHALL list the production values of `CORS_ALLOWED_ORIGINS` and `TRUSTED_HOSTS` and the Admin_Frontend production domain.

### Requirement 21: Pull Request Status Reporting

**User Story:** As a Developer, I want a single PR status summary that shows every CI workflow result, so that I do not have to click into each run.

#### Acceptance Criteria

1. WHEN a workflow listed in Requirement 1 Acceptance Criterion 1 reports its result, THE CI_System SHALL post or update a PR status check within 30 seconds whose context matches the workflow filename without the `.yml` or `.yaml` extension, and whose state is set to `success` if the workflow concluded with all required steps passing or `failure` if any required step did not pass.
2. WHEN the CI_System posts a new PR summary comment and a prior summary comment authored by the same workflow exists on the same PR, THE CI_System SHALL replace the prior summary comment's content with the new summary within 30 seconds and SHALL NOT create a duplicate summary comment on that PR.
3. WHEN the CI_System posts a new PR summary comment and no prior summary comment authored by the same workflow exists on the same PR, THE CI_System SHALL create exactly one new comment containing the summary within 30 seconds.
4. WHILE the CI_System is not in the act of posting a new PR summary comment, THE CI_System SHALL NOT modify, replace, or remove any prior PR summary comment authored by the same workflow on the same PR.

## Correctness Properties

The following properties SHALL hold across the CI/CD pipeline and SHALL be verified by the design and tasks phases that follow.

### CP-1: CI Idempotency

For every commit SHA `c` and every workflow `W` listed in Requirement 1 Acceptance Criterion 1, two runs of `W` against `c` on the same runner image SHALL produce the same conclusion (`success` or `failure`), the same set of test names with the same pass/fail outcome per test, and the same uploaded artifact filenames. Verification approach: replay the same commit twice in CI and diff the run summaries and artifact listings.

### CP-2: Deployment Atomicity

Every Production_Deploy_Workflow run SHALL satisfy the Atomic_Deploy definition: either Admin_Frontend, Admin_Backend, and LightRAG_Service all reflect the new release version, or all reflect the previous release version, at the conclusion of the run. Verification approach: deliberately fail the post-deploy Smoke_Test in a staging dry run and assert that all three components revert to the previous release version and the Vercel deployment is demoted.

### CP-3: Secret Hygiene

For every workflow run and every published container image, no value of any secret listed in Requirement 13 Acceptance Criterion 1 SHALL appear in plaintext in workflow logs, artifacts, image filesystems, or image environment variables. Verification approach: run a log-grep job and an image-filesystem scanner against representative test secrets injected only into a pre-production replay environment.

### CP-4: Upstream Isolation

For every reachable failure mode of LangGraph_Upstream (timeout, 5xx, connection refused, DNS failure), Admin_Backend SHALL continue to serve every endpoint that does not depend on LangGraph_Upstream with HTTP 200, and SHALL return HTTP 503 with Structured_Error code `LANGGRAPH_UNAVAILABLE` for every endpoint that does. Verification approach: chaos-test Admin_Backend with a mock upstream that simulates each failure mode and assert response codes per route.

### CP-5: Migration Reversibility

For every Alembic revision `r` introduced after the baseline, the sequence `alembic upgrade head; alembic downgrade base; alembic upgrade head` SHALL succeed against an ephemeral database. Verification approach: run the sequence in Backend_CI_Workflow as defined in Requirement 12.

### CP-6: Build Reproducibility

For every commit SHA `c` and every image `I` in `{admin_backend, admin_frontend, lightrag}`, two builds of `I` from `c` on the same builder image with identical build arguments SHALL produce identical application code and dependency layer digests. Verification approach: a CI job builds twice and diffs `docker buildx imagetools inspect` outputs.

### CP-7: Path-Filter Correctness

For every PR `p` whose changed file set is `F`, the set of triggered workflows SHALL equal `{ W : Path_Filter(W) ∩ F ≠ ∅ }`. Verification approach: a synthetic test repo opens PRs touching disjoint subtrees and asserts the triggered workflow set per case.

### CP-8: Health-Endpoint Consistency

For every state of LangGraph_Upstream and the circuit breaker, the response of the Health_Check_Endpoint SHALL match the rule defined in Requirement 14 Acceptance Criterion 7. Verification approach: drive the circuit breaker through closed, open, and half-open states and assert the endpoint response in each state.
