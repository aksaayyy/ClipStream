import os
import logging
from fastapi import FastAPI, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from typing import Any, Dict
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('transcriber.log')
    ]
)
logger = logging.getLogger("transcriber")

# Initialize FastAPI app
app = FastAPI(
    title="ClipStream Transcriber Service",
    description="Microservice for transcribing audio/video files using Whisper",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from app.routers import transcribe as transcribe_router
app.include_router(transcribe_router.router)

# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.error(f"HTTP error: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # Convert any bytes to strings in the error details
    def clean_errors(errors):
        cleaned = []
        for error in errors:
            if isinstance(error, dict):
                cleaned_error = {}
                for k, v in error.items():
                    if isinstance(v, (bytes, bytearray)):
                        try:
                            cleaned_error[k] = v.decode('utf-8')
                        except UnicodeDecodeError:
                            cleaned_error[k] = str(v)
                    elif isinstance(v, dict):
                        cleaned_error[k] = clean_errors([v])[0] if v else v
                    elif isinstance(v, list):
                        cleaned_error[k] = clean_errors(v)
                    else:
                        cleaned_error[k] = v
                cleaned.append(cleaned_error)
            elif isinstance(error, (list, tuple)):
                cleaned.append(clean_errors(error))
            elif isinstance(error, (bytes, bytearray)):
                try:
                    cleaned.append(error.decode('utf-8'))
                except UnicodeDecodeError:
                    cleaned.append(str(error))
            else:
                cleaned.append(error)
        return cleaned

    # Log the error with cleaned data
    logger.error(f"Validation error: {str(exc)}\n{exc.errors()}")
    
    # Return a safe response with cleaned error details
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False, 
            "error": "Invalid request data", 
            "details": clean_errors(exc.errors())
        },
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Convert bytes to string if needed
    error_message = str(exc)
    if isinstance(exc, (bytes, bytearray)):
        try:
            error_message = exc.decode('utf-8')
        except UnicodeDecodeError:
            error_message = str(exc)
    
    # Log the error
    logger.error(f"Unexpected error: {error_message}\n{traceback.format_exc()}")
    
    # Return a safe error response
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False, 
            "error": f"Internal server error: {error_message}",
            "error_type": exc.__class__.__name__
        },
    )

# Health check endpoint
@app.get("/health", include_in_schema=False)
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "transcriber",
        "version": app.version,
        "environment": os.getenv("ENV", "development"),
    }

# Root endpoint
@app.get("/", include_in_schema=False)
async def root() -> Dict[str, str]:
    """Root endpoint with service information"""
    return {
        "service": "ClipStream Transcriber",
        "version": app.version,
        "docs": "/docs",
        "health_check": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5002")),
        reload=os.getenv("ENV", "development") == "development"
    )
