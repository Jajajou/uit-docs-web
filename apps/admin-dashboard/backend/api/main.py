"""Admin dashboard API - contract-aligned /web BFF."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.config import settings
from api.errors import ApiServiceError, build_error_response
from api.routers.admin import router as admin_router
from api.routers.analytics import router as analytics_router
from api.routers.auth import router as auth_router
from api.routers.chat import router as chat_router
from api.routers.documents import router as documents_router
from api.routers.jobs import router as jobs_router
from api.routers.reviews import router as reviews_router
from api.routers.student_chat import router as student_chat_router
from api.routers.submissions import router as submissions_router
from api.routers.upload import router as upload_router
from api.security import apply_security_headers, build_https_redirect_response, enforce_trusted_host


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="UIT Admin Dashboard API",
    description="Contract-aligned BFF for the /web workspace.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id

    try:
        enforce_trusted_host(request)
    except ApiServiceError as exc:
        return apply_security_headers(build_error_response(request, exc))

    redirect = build_https_redirect_response(request)
    if redirect is not None:
        redirect.headers["x-request-id"] = request_id
        return apply_security_headers(redirect)

    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return apply_security_headers(response)


@app.exception_handler(ApiServiceError)
async def api_service_error_handler(request: Request, exc: ApiServiceError):
    return apply_security_headers(build_error_response(request, exc))


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    response = JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "unhandled_error",
                "message": (
                    str(exc)
                    if settings.TEST_MODE or settings.EXPOSE_ERROR_DETAILS
                    else "An unexpected server error occurred."
                ),
                "status": 500,
                "requestId": getattr(request.state, "request_id", None),
                "details": None,
            }
        },
    )
    if getattr(request.state, "request_id", None):
        response.headers["x-request-id"] = request.state.request_id
    return apply_security_headers(response)


app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])
app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])
app.include_router(student_chat_router, prefix="/api/student", tags=["Student Chat"])
app.include_router(upload_router, prefix="/api/uploads", tags=["Uploads"])
app.include_router(upload_router, prefix="/api/upload", tags=["Legacy Upload"])
app.include_router(documents_router, prefix="/api/documents", tags=["Documents"])
app.include_router(submissions_router, prefix="/api/submissions", tags=["Submissions"])
app.include_router(reviews_router, prefix="/api/reviews", tags=["Reviews"])
app.include_router(jobs_router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])
app.include_router(analytics_router, prefix="/api/analytics", tags=["Analytics"])


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "admin-dashboard-api", "version": "0.2.0"}


@app.get("/")
async def root():
    return {
        "message": "UIT Admin Dashboard API",
        "docs": "/docs",
        "version": "0.2.0",
    }
