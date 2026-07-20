"""
BiasLens Backend - FastAPI Application Entry Point

This module serves as the main entry point for the BiasLens backend API.
It configures CORS, middleware, route handlers, and application lifecycle events.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import analysis, candidates, dashboard, health, job_descriptions
from app.core.config import settings
from app.core.database import engine, init_db
from app.core.exceptions import BiasLensException
from app.core.logging import configure_logging
from app.ml.model_loader import ModelLoader

# Configure structured logging
configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan context manager for startup and shutdown events.
    
    Handles:
    - Database initialization
    - ML model loading and caching
    - Resource cleanup on shutdown
    """
    logger.info("Starting BiasLens backend application")
    
    # Initialize database tables
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # Pre-load NLP models to avoid cold start latency
    try:
        model_loader = ModelLoader()
        await model_loader.preload_models()
        logger.info("NLP models loaded and cached")
    except Exception as e:
        logger.error(f"Failed to load NLP models: {e}")
        # Don't fail startup, but log the error
    
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down BiasLens backend")
    await engine.dispose()
    logger.info("Database connections closed")


# Initialize FastAPI application
app = FastAPI(
    title="BiasLens API",
    description="API for analyzing unconscious bias in recruitment processes",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)


# CORS configuration for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Page-Size"],
)


# Add GZip compression for responses over 1KB
app.add_middleware(GZipMiddleware, minimum_size=1000)


# Trusted host middleware for production security
if settings.ENVIRONMENT == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware to log all incoming requests with timing information.
    """
    import time
    
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    
    # Log request details
    logger.info(
        f"{request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "process_time": f"{process_time:.3f}s",
            "client_host": request.client.host if request.client else None,
        },
    )
    
    # Add custom header with processing time
    response.headers["X-Process-Time"] = str(process_time)
    
    return response


@app.exception_handler(BiasLensException)
async def biaslens_exception_handler(request: Request, exc: BiasLensException):
    """
    Custom exception handler for BiasLens-specific errors.
    """
    logger.error(
        f"BiasLens error: {exc.message}",
        extra={
            "error_code": exc.error_code,
            "path": request.url.path,
            "details": exc.details,
        },
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Handler for standard HTTP exceptions.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handler for Pydantic validation errors.
    """
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        })
    
    logger.warning(
        f"Validation error on {request.url.path}",
        extra={"errors": errors},
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": errors,
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Catch-all handler for unexpected errors.
    """
    logger.exception(
        f"Unexpected error on {request.url.path}",
        exc_info=exc,
    )
    
    # Don't expose internal error details in production
    if settings.ENVIRONMENT == "production":
        message = "An unexpected error occurred. Please contact support."
    else:
        message = str(exc)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": message,
            }
        },
    )


# Include API routers with versioning
API_V1_PREFIX = "/api/v1"

app.include_router(
    health.router,
    prefix=API_V1_PREFIX,
    tags=["health"],
)

app.include_router(
    job_descriptions.router,
    prefix=f"{API_V1_PREFIX}/job-descriptions",
    tags=["job-descriptions"],
)

app.include_router(
    candidates.router,
    prefix=f"{API_V1_PREFIX}/candidates",
    tags=["candidates"],
)

app.include_router(
    analysis.router,
    prefix=f"{API_V1_PREFIX}/analysis",
    tags=["analysis"],
)

app.include_router(
    dashboard.router,
    prefix=f"{API_V1_PREFIX}/dashboard",
    tags=["dashboard"],
)


@app.get("/", include_in_schema=False)
async def root():
    """
    Root endpoint with API information and links.
    """
    return {
        "service": "BiasLens API",
        "version": "1.0.0",
        "status": "operational",
        "documentation": "/api/docs",
        "health_check": "/api/v1/health",
    }


if __name__ == "__main__":
    import uvicorn
    
    # Run with uvicorn for development
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
    )