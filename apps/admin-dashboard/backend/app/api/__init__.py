"""HTTP route modules for ``Admin_Backend`` (cicd-deploy-admin-dashboard).

Each submodule exposes a ``setup_<name>(app, ...)`` helper that
:func:`app.main.create_app` calls after middleware installation.  Keeping
routes in dedicated modules avoids import-time side effects on the
FastAPI ``app`` object and lets each task wire a single concern in
isolation (task 9.5 wires ``/healthz``; task 10.5 wires ``/metrics``).
"""
