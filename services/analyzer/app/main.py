import os
import sys
import logging
import json
from fastapi import FastAPI, HTTPException, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from typing import Any, Dict, Optional
import traceback
from loguru import logger
import time
from contextlib import asynccontextmanager

# Configure loguru logger
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)
logger.add("analyzer.log", rotation="10 MB", level="DEBUG")  # Log to file

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('analyzer.log')
    ]
)

# Middleware for request/response logging
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url}")
    logger.debug(f"Headers: {dict(request.headers)}")
    
    # Process the request
    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}\n{traceback.format_exc()}")
        raise
    
    # Log response
    process_time = (time.time() - start_time) * 1000
    logger.info(f"Response: {response.status_code} (took {process_time:.2f}ms)")
    
    return response

# Initialize FastAPI app
app = FastAPI(
    title="ClipStream Analyzer Service",
    description="Service for analyzing video transcripts and identifying viral moments",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add middleware
app.middleware('http')(log_requests)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from app.routers import analyze as analyze_router
app.include_router(analyze_router.router)

# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    error_detail = str(exc.detail) if exc.detail else "An error occurred"
    logger.error(f"HTTP error: {error_detail}")
    
    # Log request body if available
    try:
        body = await request.body()
        if body:
            logger.debug(f"Request body: {body.decode()}")
    except Exception as e:
        logger.warning(f"Could not log request body: {str(e)}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": error_detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    error_details = []
    for error in exc.errors():
        error_details.append({
            "loc": error["loc"],
            "msg": error["msg"],
            "type": error["type"]
        })
    
    logger.error(f"Validation error: {error_details}")
    
    # Log request body if available
    try:
        body = await request.body()
        if body:
            logger.debug(f"Request body: {body.decode()}")
    except Exception as e:
        logger.warning(f"Could not log request body: {str(e)}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False, 
            "error": "Validation error", 
            "details": error_details
        },
    )

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception) -> JSONResponse:
    error_id = f"err_{int(time.time())}"
    error_message = f"An unexpected error occurred. Error ID: {error_id}"
    
    # Log the full error with traceback
    logger.critical(
        f"Unhandled error (ID: {error_id}): {str(exc)}\n"
        f"Path: {request.url}\n"
        f"Method: {request.method}\n"
        f"Client: {request.client}\n"
        f"Traceback: {traceback.format_exc()}"
    )
    
    # Log request body if available
    try:
        body = await request.body()
        if body:
            logger.debug(f"Request body: {body.decode()}")
    except Exception as e:
        logger.warning(f"Could not log request body: {str(e)}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False, 
            "error": error_message,
            "error_id": error_id
        },
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # This is a fallback for any other unhandled exceptions
    error_id = f"err_{int(time.time())}"
    error_message = f"An unexpected error occurred. Error ID: {error_id}"
    
    # Log the full error with traceback
    logger.critical(
        f"Unhandled exception (ID: {error_id}): {str(exc)}\n"
        f"Type: {type(exc).__name__}\n"
        f"Path: {request.url}\n"
        f"Method: {request.method}\n"
        f"Client: {request.client}\n"
        f"Traceback: {traceback.format_exc()}"
    )
    
    # Log request body if available
    try:
        body = await request.body()
        if body:
            logger.debug(f"Request body: {body.decode()}")
    except Exception as e:
        logger.warning(f"Could not log request body: {str(e)}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False, 
            "error": error_message,
            "error_id": error_id
        },
    )

# Health check endpoint
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    try:
        # Perform basic health checks
        health_info = {
            "status": "healthy",
            "service": "clip-analyzer",
            "version": "0.1.0",
            "timestamp": time.time(),
            "environment": os.getenv("ENVIRONMENT", "development"),
            "python_version": sys.version,
            "system": {
                "platform": sys.platform,
                "process_id": os.getpid(),
                "cpu_count": os.cpu_count(),
                "memory_usage": {
                    "rss_mb": os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / (1024. ** 2),
                    "available_mb": os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_AVPHYS_PAGES') / (1024. ** 2)
                } if hasattr(os, 'sysconf') and hasattr(os.sysconf, '__getitem__') else {}
            },
            "dependencies": {
                "transformers": None,  # Will be populated if available
                "sentence_transformers": None,
                "torch": None
            }
        }
        
        # Try to import and get versions of key dependencies
        try:
            import transformers
            health_info["dependencies"]["transformers"] = transformers.__version__
        except ImportError:
            health_info["dependencies"]["transformers"] = "not installed"
            
        try:
            import sentence_transformers
            health_info["dependencies"]["sentence_transformers"] = sentence_transformers.__version__
        except ImportError:
            health_info["dependencies"]["sentence_transformers"] = "not installed"
            
        try:
            import torch
            health_info["dependencies"]["torch"] = torch.__version__
        except ImportError:
            health_info["dependencies"]["torch"] = "not installed"
        
        return health_info
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}"
        )

# Root endpoint
@app.get("/")
async def root() -> Dict[str, str]:
    """Root endpoint with service information."""
    return {
        "service": "ClipStream Analyzer",
        "version": "0.1.0",
        "docs": "/docs",
        "description": "Service for analyzing video transcripts and identifying viral moments"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=5003,
        reload=True,
        log_level="info"
    )
