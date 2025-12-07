"""
Production-grade FastAPI server for Document Analyzer microservice.

Features:
- Async file upload and processing
- Structured JSON logging
- Health/readiness probes
- Error handling with proper HTTP status codes
- Request validation
- Configurable via environment variables
"""

import os
import uuid
import time
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from document_analyzer import DocumentAnalyzer


# ============================================================================
# Configuration
# ============================================================================

class Config:
    """Application configuration from environment variables."""

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    WORKERS: int = int(os.getenv("WORKERS", "1"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Storage
    OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "/app/data/output"))
    TEMP_DIR: Path = Path(os.getenv("TEMP_DIR", "/app/data/temp"))
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "100"))

    # Processing
    DOCLING_CACHE_DIR: str = os.getenv("DOCLING_CACHE_DIR", "/app/.docling")

    # CORS
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    @classmethod
    def setup_directories(cls):
        """Ensure required directories exist."""
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging():
    """Configure structured JSON logging for production."""

    class JSONFormatter(logging.Formatter):
        """Custom JSON formatter for structured logging."""

        def format(self, record: logging.LogRecord) -> str:
            log_data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }

            # Add exception info if present
            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)

            # Add extra fields
            if hasattr(record, 'job_id'):
                log_data["job_id"] = record.job_id

            import json
            return json.dumps(log_data)

    # Configure root logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    logger = logging.getLogger()
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper()))

    # Reduce noise from dependencies
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# ============================================================================
# Response Models
# ============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Health status")
    timestamp: str = Field(..., description="Current timestamp")
    version: str = Field(default="1.0.0", description="API version")


class ReadinessResponse(BaseModel):
    """Readiness check response."""
    status: str = Field(..., description="Readiness status")
    docling_ready: bool = Field(..., description="Docling converter ready")
    storage_ready: bool = Field(..., description="Storage accessible")


class AnalysisResult(BaseModel):
    """Analysis job result."""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Job status: completed, failed")
    processing_time_seconds: float = Field(..., description="Time taken to process")
    results: Optional[Dict[str, Any]] = Field(None, description="Processing results")
    error: Optional[str] = Field(None, description="Error message if failed")


# ============================================================================
# Application Lifespan
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    logger = logging.getLogger(__name__)

    # Startup
    logger.info("Starting Document Analyzer API service")
    Config.setup_directories()
    logger.info(f"Output directory: {Config.OUTPUT_DIR}")
    logger.info(f"Temp directory: {Config.TEMP_DIR}")
    logger.info(f"Max file size: {Config.MAX_FILE_SIZE_MB}MB")

    # Test Docling import
    try:
        from docling.document_converter import DocumentConverter
        _ = DocumentConverter()
        logger.info("Docling DocumentConverter initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Docling: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Document Analyzer API service")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Document Analyzer API",
    description="Production-grade microservice for PDF document analysis using Docling",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
cors_origins = Config.CORS_ORIGINS.split(",") if Config.CORS_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Liveness probe endpoint.

    Returns 200 if the service is alive.
    Used by Kubernetes liveness probe.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@app.get("/ready", response_model=ReadinessResponse, tags=["Health"])
async def readiness_check():
    """
    Readiness probe endpoint.

    Returns 200 if the service is ready to handle requests.
    Used by Kubernetes readiness probe.
    """
    logger = logging.getLogger(__name__)

    # Check if Docling is ready
    docling_ready = False
    try:
        from docling.document_converter import DocumentConverter
        _ = DocumentConverter()
        docling_ready = True
    except Exception as e:
        logger.warning(f"Docling not ready: {e}")

    # Check if storage is accessible
    storage_ready = Config.OUTPUT_DIR.exists() and Config.TEMP_DIR.exists()

    if not (docling_ready and storage_ready):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready"
        )

    return ReadinessResponse(
        status="ready",
        docling_ready=docling_ready,
        storage_ready=storage_ready,
    )


# ============================================================================
# Analysis Endpoints
# ============================================================================

@app.post("/api/v1/analyze", response_model=AnalysisResult, tags=["Analysis"])
async def analyze_document(
    file: UploadFile = File(..., description="PDF file to analyze")
):
    """
    Analyze a PDF document.

    Accepts a PDF file upload and performs:
    - Text extraction
    - Table extraction (exported as CSV)
    - Image extraction
    - Markdown conversion
    - Document statistics

    Returns job ID and results with file paths.
    """
    logger = logging.getLogger(__name__)
    job_id = str(uuid.uuid4())
    start_time = time.time()

    # Create logger with job_id context
    job_logger = logging.LoggerAdapter(logger, {'job_id': job_id})
    job_logger.info(f"Starting analysis for file: {file.filename}")

    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )

    # Validate file size
    file_size = 0
    temp_path = None

    try:
        # Save uploaded file to temp location
        temp_path = Config.TEMP_DIR / f"{job_id}_{file.filename}"

        with open(temp_path, 'wb') as f:
            while chunk := await file.read(8192):  # 8KB chunks
                file_size += len(chunk)

                # Check size limit
                if file_size > Config.MAX_FILE_SIZE_MB * 1024 * 1024:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File size exceeds {Config.MAX_FILE_SIZE_MB}MB limit"
                    )

                f.write(chunk)

        job_logger.info(f"File saved to temp: {temp_path} ({file_size} bytes)")

        # Create job-specific output directory
        job_output_dir = Config.OUTPUT_DIR / job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)

        # Run document analysis with job-specific output directory
        job_logger.info("Initializing DocumentAnalyzer")
        analyzer = DocumentAnalyzer(str(temp_path), output_dir=job_output_dir)

        job_logger.info("Starting document processing")

        # Run analysis (synchronous for now)
        try:
            analyzer.analyze()
        except Exception as e:
            job_logger.error(f"Analysis failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Document analysis failed: {str(e)}"
            )

        # Collect results
        output_stem = Path(temp_path).stem
        results = {
            "job_id": job_id,
            "markdown_path": str(job_output_dir / f"{output_stem}.md"),
            "summary_path": str(job_output_dir / f"{output_stem}_summary.json"),
            "tables": [],
            "images_dir": str(job_output_dir / f"{output_stem}_images"),
        }

        # Find generated table files
        for csv_file in job_output_dir.glob(f"{output_stem}_table_*.csv"):
            results["tables"].append(str(csv_file))

        processing_time = time.time() - start_time
        job_logger.info(f"Analysis completed in {processing_time:.2f}s")

        return AnalysisResult(
            job_id=job_id,
            status="completed",
            processing_time_seconds=round(processing_time, 2),
            results=results,
        )

    except HTTPException:
        raise
    except Exception as e:
        job_logger.error(f"Unexpected error: {e}", exc_info=True)

        processing_time = time.time() - start_time

        return AnalysisResult(
            job_id=job_id,
            status="failed",
            processing_time_seconds=round(processing_time, 2),
            error=str(e),
        )

    finally:
        # Cleanup temp file
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
                job_logger.info(f"Cleaned up temp file: {temp_path}")
            except Exception as e:
                job_logger.warning(f"Failed to cleanup temp file: {e}")


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Document Analyzer API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "api": "/api/v1/analyze",
    }


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger = logging.getLogger(__name__)
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": str(exc) if Config.LOG_LEVEL == "DEBUG" else "An unexpected error occurred",
        }
    )


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Run the FastAPI application with uvicorn."""
    setup_logging()

    logger = logging.getLogger(__name__)
    logger.info(f"Starting server on {Config.HOST}:{Config.PORT}")
    logger.info(f"Workers: {Config.WORKERS}")
    logger.info(f"Log level: {Config.LOG_LEVEL}")

    uvicorn.run(
        "api_server:app",
        host=Config.HOST,
        port=Config.PORT,
        workers=Config.WORKERS,
        log_level=Config.LOG_LEVEL.lower(),
        access_log=True,
    )


if __name__ == "__main__":
    main()
