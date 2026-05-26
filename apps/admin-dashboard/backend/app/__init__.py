"""Admin_Backend new application package.

This package hosts the modules introduced by the
``cicd-deploy-admin-dashboard`` spec (see ``app/core``, ``app/clients``,
``app/middleware``, ``app/main.py`` and friends).  It coexists with the
legacy ``api`` package; refactoring the older code into ``app`` is out
of scope for the current task.

Wiring contract for ``app/main.py`` (task 10.1):

* ``RequestLogMiddleware`` from :mod:`app.middleware.request_log` MUST
  be installed via ``app.add_middleware(RequestLogMiddleware)`` so that
  R17.5 / Property 14 (exactly one structured JSON log line per
  request) is satisfied.  Install it after the trusted-host and CORS
  middlewares so the request-id header is added to every response,
  including responses produced by upstream guards.
"""
