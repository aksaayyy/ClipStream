import os
import sys
import logging
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path

from .renderer import VideoRenderer, DEFAULT_FFMPEG_TIMEOUT

# Create logs directory if it doesn't exist
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("DEBUG") else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / f"renderer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)

# Set log level for specific loggers
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Custom exception handler for better error responses
class ClipRendererError(Exception):
    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


app = FastAPI(
    title="ClipStream Renderer",
    description="Service for rendering video clips with captions",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Add middleware for request logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}")
    try:
        response = await call_next(request)
        logger.info(f"Request completed: {request.method} {request.url} - Status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Request failed: {request.method} {request.url} - Error: {str(e)}", exc_info=True)
        raise

# Exception handlers
@app.exception_handler(ClipRendererError)
async def clip_renderer_error_handler(request: Request, exc: ClipRendererError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.message,
            "details": exc.details
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": "Validation Error",
            "details": exc.errors()
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "details": {}
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal Server Error",
            "details": {"message": str(exc) if os.environ.get("DEBUG") else "An unexpected error occurred"}
        }
    )

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the video renderer
renderer = VideoRenderer()

class RenderRequest(BaseModel):
    video: str
    format: str = "vertical"  # vertical, square, original
    add_captions: bool = True
    normalize_audio: bool = True
    output_dir: Optional[str] = None

class RenderResponse(BaseModel):
    success: bool
    clips_rendered: List[str] = []
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class VideoInfoResponse(BaseModel):
    success: bool
    video: Dict[str, Any]
    error: Optional[str] = None

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "clip-renderer",
        "version": "0.1.0"
    }

@app.get("/video/{video_name}/info", response_model=VideoInfoResponse)
async def get_video_info(video_name: str):
    """
    Get information about a video file.
    
    Args:
        video_name: Name of the video file in the downloads directory
        
    Returns:
        Video information including duration and format
    """
    try:
        video_info = renderer.get_video_info(video_name)
        if "error" in video_info:
            raise HTTPException(status_code=404, detail=video_info["error"])
            
        return VideoInfoResponse(success=True, video=video_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting video info: {str(e)}")

@app.post("/render", response_model=RenderResponse)
async def render_clips(request: RenderRequest):
    """
    Render video clips based on the provided video and clips configuration.
    
    Expected files:
    - Video: /data/downloads/{video}
    - Transcript: /data/transcripts/{video}.json
    - Clips config: /data/clips/{video}_clips.json
    
    Returns paths to rendered clips.
    """
    try:
        logger.info(f"Starting render job for video: {request.video}")
        
        # Call the renderer
        success, clips_rendered, error = renderer.render_clips(
            video_name=request.video,
            format=request.format,
            add_captions=request.add_captions,
            normalize_audio=request.normalize_audio,
            output_dir=request.output_dir
        )
        
        if not success and not clips_rendered:
            raise HTTPException(status_code=500, detail=error or "Failed to render clips")
            
        response = RenderResponse(
            success=success,
            clips_rendered=clips_rendered,
            error=error,
            details={
                "video": request.video,
                "format": request.format,
                "clips_rendered": len(clips_rendered)
            }
        )
        
        logger.info(f"Render job completed: {json.dumps(response.dict(), indent=2)}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error rendering clips: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=5004, reload=True)
