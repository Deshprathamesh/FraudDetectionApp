# ==============================================================================
# FraudGraph AI - FastAPI Application Factory
# Workstream: Person 1 (Brain) - Stage 1 Foundation
# ==============================================================================

import logging
from typing import Dict, Any
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import settings
from backend.errors import FraudGraphException, ErrorResponse
from backend.api.routes import router as api_router

logger = logging.getLogger("fraudgraph.api")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects defensive HTTP security headers into every response."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


def create_app() -> FastAPI:
    """Creates and configures the FastAPI application instance."""
    app = FastAPI(
        title="FraudGraph AI - Investigation Brain API",
        description="GraphRAG & Multi-Hop Agentic Fraud Investigation Platform",
        version="1.0.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url=None,
    )

    # 1. Security Headers Middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 2. CORS Middleware
    allowed_origins = [settings.frontend_url, "http://localhost:3000", "http://127.0.0.1:3000"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # --------------------------------------------------------------------------
    # Centralized Section 9 Error Handlers
    # --------------------------------------------------------------------------

    @app.exception_handler(FraudGraphException)
    async def handle_fraudgraph_exception(request: Request, exc: FraudGraphException):
        """Maps internal typed domain exceptions directly to Section 9 responses."""
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        """Transforms Pydantic validation errors into Section 9 error dictionary."""
        errors_summary = []
        for err in exc.errors():
            loc = " -> ".join(str(l) for l in err.get("loc", []))
            msg = err.get("msg", "Validation error")
            errors_summary.append(f"{loc}: {msg}")

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "; ".join(errors_summary) or "Invalid request parameters.",
                    "details": {"validation_errors": exc.errors()},
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        """Transforms HTTP exceptions into Section 9 format."""
        code_map = {
            404: "NOT_FOUND",
            403: "FORBIDDEN",
            401: "UNAUTHORIZED",
            400: "BAD_REQUEST",
            405: "METHOD_NOT_ALLOWED",
            504: "GATEWAY_TIMEOUT",
        }
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code_map.get(exc.status_code, "HTTP_ERROR"),
                    "message": str(exc.detail),
                    "details": {},
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception):
        """
        Global safety net: logs full error internally, but strictly prevents
        stack trace or system path leakage to the caller per Section 9.
        """
        logger.error(f"Unhandled server error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected internal server error occurred.",
                    "details": {},
                }
            },
        )

    # --------------------------------------------------------------------------
    # Root Liveness Endpoint & Route Mounting
    # --------------------------------------------------------------------------

    @app.get("/health", tags=["Health"])
    async def root_health():
        return {"status": "healthy", "service": "fraudgraph-backend", "version": "1.0.0"}

    # Mount API Router under /api
    app.include_router(api_router, prefix="/api")

    return app


# Default ASGI application instance
app = create_app()
