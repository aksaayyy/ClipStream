import os
import time
import json
import shutil
import tempfile
import threading
import traceback
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from pydantic import BaseModel, Field, validator, HttpUrl
from loguru import logger

# Import our downloader
from .downloader import YouTubeDownloader
from collections import defaultdict

# In-memory rate limiter
class RateLimiter:
    def __init__(self, times: int, seconds: int):
        self.times = times
        self.seconds = seconds
        self.requests = defaultdict(list)
    
    async def __call__(self, request: Request):
        client = request.client.host
        now = datetime.now()
        
        # Clean up old requests
        self.requests[client] = [t for t in self.requests[client] if now - t < timedelta(seconds=self.seconds)]
        
        if len(self.requests[client]) >= self.times:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {self.times} requests per {self.seconds} seconds"
            )
        
        self.requests[client].append(now)
        return True

from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, Dict, Any
import yt_dlp
import os
import logging
from pathlib import Path
from datetime import datetime, timedelta
import uvicorn
import secrets
import asyncio

# Constants
# Default to 2GB max file size, can be overridden by environment variable
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 2000))  # 2000MB (2GB) default max file size
MAX_VIDEO_LENGTH = int(os.getenv("MAX_VIDEO_LENGTH", 7200))  # 2 hours in seconds default max length
RATE_LIMIT = os.getenv("RATE_LIMIT", "100/day")  # Rate limiting

logger.info(f"Configuration - Max File Size: {MAX_FILE_SIZE_MB}MB, Max Video Length: {MAX_VIDEO_LENGTH}s, Rate Limit: {RATE_LIMIT}")

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("yt-fetcher")

# Enable debug logging for uvicorn and fastapi
logging.getLogger("uvicorn").setLevel(logging.DEBUG)
logging.getLogger("uvicorn.access").setLevel(logging.DEBUG)
logging.getLogger("fastapi").setLevel(logging.DEBUG)

app = FastAPI(
    title="ClipStream YT-Fetcher",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting configuration
rate_limiter = RateLimiter(times=100, seconds=86400)  # 100 requests per day

# Custom exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# Ensure download directory exists
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "downloads"))
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
logger.info(f"Using download directory: {os.path.abspath(DOWNLOAD_DIR)}")

# Initialize the downloader
from .downloader import YouTubeDownloader
downloader = YouTubeDownloader(download_dir=DOWNLOAD_DIR)

# Track active downloads to prevent duplicates
active_downloads: Dict[str, Dict[str, Any]] = {}
DOWNLOAD_TIMEOUT = 300  # 5 minutes timeout per download

class DownloadRequest(BaseModel):
    url: HttpUrl
    format: Optional[str] = Field("mp4", pattern=r'^\w+$')
    request_id: Optional[str] = None  # For tracking downloads

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "format": "mp4"
            }
        }

class DownloadResponse(BaseModel):
    success: bool
    filename: str
    duration: str
    path: str
    title: Optional[str] = None
    error: Optional[str] = None

def get_video_info(url: str, request_id: str) -> dict:
    """Get video info with timeout and size validation"""
    logger.debug(f"Getting video info for request {request_id}")
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': False,
            'socket_timeout': 30,  # 30 seconds timeout
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Check video duration
            video_duration = info.get('duration', 0)
            if video_duration > MAX_VIDEO_LENGTH:
                raise ValueError(f"Video is too long. Duration: {video_duration}s, maximum allowed: {MAX_VIDEO_LENGTH} seconds")
                
            # Check if video is age-restricted or private
            if info.get('age_limit', 0) > 0:
                raise HTTPException(
                    status_code=403,
                    detail="Age-restricted content is not supported"
                )
                
            if info.get('availability') == 'private':
                raise HTTPException(
                    status_code=403,
                    detail="Private videos are not supported"
                )
                
            return {
                'title': info.get('title', 'untitled'),
                'duration': info.get('duration', 0),
                'ext': info.get('ext', 'mp4'),
                'filesize': info.get('filesize_approx') or info.get('filesize')
            }
            
    except yt_dlp.DownloadError as e:
        if 'Private video' in str(e):
            raise HTTPException(status_code=403, detail="This is a private video") from e
        if 'is not a valid URL' in str(e):
            raise HTTPException(status_code=400, detail="Invalid URL") from e
        if 'Video unavailable' in str(e):
            raise HTTPException(status_code=404, detail="Video not found or unavailable") from e
        logger.error(f"Download error for request {request_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching video info: {str(e)}") from e
        
    except Exception as e:
        logger.error(f"Unexpected error getting video info for request {request_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error processing video") from e
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'untitled'),
                'duration': info.get('duration', 0),
                'ext': info.get('ext', 'mp4')
            }
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        raise

def download_video(url: str, output_dir: str, request_id: str, max_retries: int = 3) -> dict:
    """Download video with enhanced error handling, retries, and progress reporting"""
    active_downloads[request_id] = {
        "status": "downloading",
        "start_time": datetime.utcnow(),
        "progress": "0%",
        "speed": "0 B/s",
        "eta": "Unknown"
    }
    
    last_error = None
    downloaded_file = None
    
    # Progress hook function
    def progress_hook(d):
        if d['status'] == 'downloading':
            active_downloads[request_id].update({
                'status': 'downloading',
                'progress': d.get('_percent_str', '0%'),
                'speed': d.get('_speed_str', '0 B/s'),
                'eta': d.get('_eta_str', 'Unknown')
            })
        elif d['status'] == 'finished':
            active_downloads[request_id].update({
                'status': 'post-processing',
                'progress': '100%',
                'speed': '0 B/s',
                'eta': 'Processing...'
            })
    
    for attempt in range(max_retries):
        try:
            # Get video info first
            video_info = get_video_info(url, f"{request_id}_info_attempt{attempt}")
            
            # Generate safe filename
            safe_title = "".join(c if c.isalnum() or c in ' -_' else '_' for c in video_info['title'])
            output_template = f"{safe_title}.%(ext)s"
            output_path = os.path.join(output_dir, output_template.replace('%(ext)s', 'mp4'))
            
            # Check if file already exists and is complete
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                if file_size > 0 and file_size < MAX_FILE_SIZE_MB * 1024 * 1024:
                    logger.info(f"File already exists and appears complete: {output_path}")
                    return {
                        "success": True,
                        "filename": os.path.basename(output_path),
                        "title": video_info.get('title', 'Unknown'),
                        "duration": str(timedelta(seconds=int(video_info.get('duration', 0)))),
                        "path": output_path,
                        "size_mb": file_size / (1024 * 1024)
                    }
            
            ydl_opts = {
                # Optimized format selection for speed and quality
                # Prefer pre-merged formats first (faster), then fall back to separate streams
                'format': 'bestvideo[ext=mp4][height<=?1080][fps<=?60]+bestaudio[ext=m4a]/'
                         'bestvideo[height<=?1080][fps<=?60]+bestaudio/best[height<=?1080]',
                'outtmpl': os.path.join(output_dir, output_template),
                # Performance optimizations
                'socket_timeout': 60,  # Reduced timeout for faster failure
                'extract_flat': False,
                'noplaylist': True,
                'nocheckcertificate': True,
                'ignoreerrors': False,
                'no_warnings': False,
                'quiet': False,
                # Faster download settings
                'http_chunk_size': 2097152,  # 2MB chunks for better progress tracking
                'fragment_retries': 3,
                'retries': 3,
                'file_access_retries': 3,
                'extractor_retries': 2,
                'skip_unavailable_fragments': True,
                'keep_fragments': False,
                'concurrent_fragment_downloads': 8,  # Increased parallelism
                'throttledratelimit': 10000000,  # 10MB/s rate limit (adjust as needed)
                # Post-processing
                'merge_output_format': 'mp4',
                'postprocessors': [
                    # Fastest possible remuxing
                    {
                        'key': 'FFmpegVideoConvertor',
                        'preferedformat': 'mp4',
                        'when': 'video'  # Only convert if necessary
                    },
                    # Optimized audio settings
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'aac',
                        'preferredquality': '192',
                    }
                ],
                'ffmpeg_location': 'ffmpeg',
                'postprocessor_args': {
                    # Faster encoding with good quality
                    'ffmpeg': [
                        '-c:v', 'libx264',
                        '-preset', 'fast',  # Faster encoding
                        '-crf', '22',  # Slightly higher CRF for smaller files (23 is default)
                        '-movflags', '+faststart',
                        '-c:a', 'aac',
                        '-b:a', '192k',  # Slightly lower audio bitrate
                        '-threads', '0'  # Use all available threads
                    ]
                },
                # Progress and logging
                'progress_hooks': [progress_hook],
                'noprogress': False,
                'progress_with_newline': True,
                'logger': logger,
                # Performance tweaks
                'extractor_args': {
                    'youtube': {
                        'skip': ['dash', 'hls'],  # Skip DASH/HLS for faster format selection
                        'player_client': ['android', 'web']  # Prefer mobile formats (often faster)
                    }
                },
                'format_sort': [
                    'res:1080', 'res:720', 'res:480',  # Prefer 1080p or lower
                    'vcodec:h264',  # Prefer H.264 for better compatibility
                    'acodec:aac',  # Prefer AAC audio
                    'fps',  # Prefer higher FPS
                    'size',  # Prefer smaller files
                    'tbr',  # Prefer lower total bitrate
                ],
                'format_sort_force': True,
                'retry_sleep_functions': {
                    'http': lambda n: 2 * (2 ** (n - 1)),  # Faster retry backoff
                    'fragment': lambda n: 2 * (2 ** (n - 1)),
                    'extractor': lambda n: 2 * (2 ** (n - 1)),
                },
                # Cache settings
                'cachedir': False,
                'youtube_include_dash_manifest': False,  # Disable DASH for faster format selection
                'youtube_include_hls_manifest': False,  # Disable HLS for faster format selection
            }
            
            logger.info(f"Starting download (attempt {attempt + 1}/{max_retries}): {url}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                
                # Get the actual downloaded file path
                downloaded_file = ydl.prepare_filename(info_dict)
                if not os.path.exists(downloaded_file):
                    # Try to find the file with mp4 extension
                    downloaded_file = os.path.splitext(downloaded_file)[0] + '.mp4'
                
                if not os.path.exists(downloaded_file):
                    raise FileNotFoundError("Downloaded file not found after completion")
                
                file_size = os.path.getsize(downloaded_file)
                if file_size == 0:
                    raise ValueError("Downloaded file is empty")
                
                # Update status
                active_downloads[request_id].update({
                    'status': 'completed',
                    'progress': '100%',
                    'speed': '0 B/s',
                    'eta': 'Completed'
                })
                
                return {
                    "success": True,
                    "filename": os.path.basename(downloaded_file),
                    "title": info_dict.get('title', 'Unknown'),
                    "duration": str(timedelta(seconds=int(info_dict.get('duration', 0)))),
                    "path": downloaded_file,
                    "size_mb": file_size / (1024 * 1024)
                }
                
        except Exception as e:
            last_error = str(e)
            logger.error(f"Download attempt {attempt + 1} failed: {last_error}")
            if attempt < max_retries - 1:
                retry_delay = 5 * (2 ** attempt)  # Exponential backoff
                logger.info(f"Retrying in {retry_delay} seconds... (attempt {attempt + 2}/{max_retries})")
                time.sleep(retry_delay)
            continue
        finally:
            # Clean up if this was the last attempt and it failed
            if attempt == max_retries - 1 and 'downloaded_file' in locals() and os.path.exists(downloaded_file):
                try:
                    os.remove(downloaded_file)
                except Exception as e:
                    logger.warning(f"Failed to clean up file {downloaded_file}: {e}")
    
    # If we get here, all attempts failed
    error_msg = f"All {max_retries} download attempts failed. Last error: {last_error}"
    logger.error(error_msg)
    active_downloads[request_id].update({
        'status': 'failed',
        'error': error_msg,
        'progress': '0%',
        'speed': '0 B/s',
        'eta': 'Failed'
    })
    raise Exception(error_msg)

@app.post("/fetch", response_model=DownloadResponse)
async def fetch_video(request: Request, download_request: DownloadRequest):
    """Download a video from YouTube with enhanced error handling and progress tracking"""
    # Initialize downloader
    downloader = YouTubeDownloader(download_dir=DOWNLOAD_DIR)

    # Validate rate limiting
    rate_limiter = RateLimiter(times=5, seconds=60)  # 5 requests per minute
    rate_limiter(request)
    
    # Generate request ID if not provided
    if not download_request.request_id:
        download_request.request_id = f"dl_{str(uuid.uuid4())[:8]}"
    
    request_id = download_request.request_id
    
    # Check for duplicate request
    if request_id in active_downloads:
        existing = active_downloads[request_id]
        if existing['status'] == 'downloading':
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "Duplicate request detected",
                    "message": "A download with this ID is already in progress",
                    "request_id": request_id,
                    "status": "in_progress"
                }
            )
    
    # Initialize download status
    active_downloads[request_id] = {
        "status": "starting",
        "start_time": datetime.utcnow().isoformat(),
        "progress": "0%",
        "speed": "0 B/s",
        "eta": "Unknown",
        "url": str(download_request.url)
    }
    
    # Start download in background
    try:
        try:
            # Run download in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: downloader.download_video(
                    url=str(download_request.url),
                    request_id=request_id,
                    max_retries=3
                )
            )
            
            if not result.get('success', False):
                error_msg = result.get('error', 'Unknown error during download')
                logger.error(f"Download failed: {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error_msg
                )
            
            # Clean up the active download after successful completion
            if request_id in active_downloads:
                del active_downloads[request_id]
            
            # Ensure the file exists before returning success
            if not os.path.exists(result['path']):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Download completed but file not found"
                )
            
            return DownloadResponse(
                success=True,
                filename=result['filename'],
                title=result['title'],
                duration=str(timedelta(seconds=int(result['duration']))),
                path=result['path']
            )
            
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
            
        except Exception as e:
            logger.error(f"Error in download process: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Download failed: {str(e)}"
            )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
        
    except Exception as e:
        logger.error(f"Error in fetch_video: {str(e)}", exc_info=True)
        
        # Update status with error
        if request_id in active_downloads:
            active_downloads[request_id].update({
                'status': 'error',
                'error': str(e),
                'end_time': datetime.utcnow().isoformat()
            })
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing your request: {str(e)}"
        )
    finally:
        # Clean up - remove from active downloads in all cases
        if request_id in active_downloads:
            del active_downloads[request_id]
            logger.debug(f"Cleaned up request {request_id} from active downloads")

@app.get("/info", response_model=Dict[str, Any])
async def get_video_info_endpoint(url: str):
    """Get video information without downloading."""
    try:
        # Generate a unique request ID
        request_id = f"info_{secrets.token_hex(4)}"
        logger.info(f"Getting info for URL: {url}")
        
        # Get video info using the downloader
        info = downloader.get_video_info(url)
        
        if not info:
            raise HTTPException(status_code=404, detail="Video not found")
            
        return {
            "title": info.get("title", ""),
            "duration": info.get("duration", 0),
            "ext": info.get("ext", "mp4"),
            "filesize": info.get("filesize")
        }
        
    except HTTPException as e:
        raise
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting video info: {str(e)}")

@app.get("/test/ytdlp")
async def test_ytdlp(url: str):
    """Test endpoint with simplified yt-dlp configuration"""
    ydl_opts = {
        'format': 'best[height<=1080]',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': False,
        'extract_flat': False,
        'forcejson': True,
        'nocheckcertificate': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "status": "success",
                "title": info.get('title'),
                "duration": info.get('duration'),
                "formats": len(info.get('formats', []))
            }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "type": type(e).__name__
        }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "yt-fetcher"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
