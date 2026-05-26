"""HTTP middlewares for ``Admin_Backend``.

This package hosts middlewares introduced by the
``cicd-deploy-admin-dashboard`` spec.

* :mod:`request_log` — emits exactly one JSON log line per request with
  the fields required by R17.5 / design C13 / Property 14
  (``timestamp``, ``request_id``, ``method``, ``path``, ``status``,
  ``duration_ms``, ``user_id_hash``).
"""

from .request_log import RequestLogMiddleware

__all__ = ["RequestLogMiddleware"]
