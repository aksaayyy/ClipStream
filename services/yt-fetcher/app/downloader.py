import os
import time
import logging
import json
import re
import tempfile
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List, Callable, Union
from urllib.parse import urlparse, parse_qs
import yt_dlp
from loguru import logger

# Default download options
DEFAULT_YTDL_OPTS = {
    # Video format selection
    'format': 'bestvideo[ext=mp4][height<=?1080][fps<=?30]+bestaudio[ext=m4a]/best[ext=mp4]/best',
    'merge_output_format': 'mp4',
    'outtmpl': '%(title).200s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    
    # Network and retry settings
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': False,
    'no_warnings': False,
    'extract_flat': False,
    'forcejson': True,
    'cachedir': False,
    'retries': 10,
    'fragment_retries': 10,
    'file_access_retries': 10,
    'extractor_retries': 3,
    'concurrent_fragment_downloads': 4,
    'socket_timeout': 30,
    'extractor_retries': 3,
    'buffersize': 1024 * 1024,  # 1MB buffer size
    'http_chunk_size': 10485760,  # 10MB chunks
    
    # HTTP Headers to mimic a real browser
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
        'Referer': 'https://www.youtube.com/',
        'Origin': 'https://www.youtube.com',
        'Sec-Ch-Ua': '"Microsoft Edge";v="125", "Chromium";v="125", ".Not/A)Brand";v="24"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"macOS"',
    },
    
    # YouTube specific settings
    'youtube_include_dash_manifest': False,
    'youtube_include_hls_manifest': False,
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
            'player_skip': ['configs', 'webpage', 'js'],
            'skip': ['dash', 'hls'],
            'nocheckcertificate': True,
        }
    },
    
    # Post-processing
    'postprocessors': [{
        'key': 'FFmpegVideoConvertor',
        'preferedformat': 'mp4',
    }],
    
    # Cookies and cache
    'cookiefile': None,  # Set path to cookies.txt if needed
    'noplaylist': True,
    'ignore_no_formats_error': True,
    'extract_flat': False,
    
    # Debugging
    'verbose': True,
    'dump_intermediate_pages': True,
    'writeinfojson': False,
    
    # Thumbnails and metadata
    'writethumbnail': True,
    'write_all_thumbnails': False,
    'writedescription': True,
    'writeannotations': True,
    'writesubtitles': False,
    'writeautomaticsub': False,
    'allsubtitles': False,
    
    # Rate limiting
    'ratelimit': None,  # bytes per second (e.g., 50K or 4.2M)
    'throttledratelimit': None,  # bytes per second when throttled
    'retries': 10,
    'file_access_retries': 10,
    'fragment_retries': 10,
    'extractor_retries': 3,
    'skip_unavailable_fragments': True,
    'keep_fragments': True,
    'extract_flat': False,
    'live_from_start': False,
}

class YouTubeDownloader:
    """YouTube video downloader using yt-dlp with enhanced error handling and progress reporting."""
    
    def __init__(self, download_dir: str = "downloads", max_retries: int = 3, max_workers: int = 3):
        """Initialize the YouTube downloader with yt-dlp.
        
        Args:
            download_dir: Directory to save downloaded videos
            max_retries: Maximum number of retry attempts for downloads
            max_workers: Maximum number of concurrent downloads
        """
        self.download_dir = Path(download_dir).expanduser().resolve()
        self.max_retries = max(1, max_retries)
        self.active_downloads: Dict[str, Dict[str, Any]] = {}
        
        # Create download directory if it doesn't exist
        self.download_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Download directory: {self.download_dir}")
        
        # Initialize thread pool for concurrent downloads
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # Configure yt-dlp options
        self.ytdl_opts = self._get_ytdl_opts()
    
    def _get_ytdl_opts(self) -> dict:
        """Get yt-dlp options with proper configuration."""
        return {
            'format': 'best[height<=1080]',
            'outtmpl': str(self.download_dir / '%(title).200s.%(ext)s'),
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
            # Add back necessary options from DEFAULT_YTDL_OPTS
            'restrictfilenames': True,
            'retries': 10,
            'fragment_retries': 10,
            'file_access_retries': 10,
            'extractor_retries': 3,
        }
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to be filesystem-safe."""
        # Remove invalid characters
        filename = re.sub(r'[\\/*?:"<>|]', "", filename)
        # Replace spaces and dots with underscores
        filename = re.sub(r'[\s.]+', "_", filename)
        # Remove leading/trailing underscores
        return filename.strip('_')

    def get_video_info(self, url: str) -> Dict[str, Any]:
        """Get video information without downloading.
        
        Args:
            url: YouTube video URL
            
        Returns:
            Dict containing video metadata
            
        Raises:
            ValueError: If there's an error fetching video info or no suitable streams found
        """
        try:
            logger.info(f"Fetching video info for URL: {url}")
            
            # Configure yt-dlp to only extract info, not download
            ydl_opts = self.ytdl_opts.copy()
            ydl_opts.update({
                'skip_download': True,
                'extract_flat': False,
                'forcejson': True,
                'simulate': True,
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
            })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract video info
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    raise ValueError("No video information found")
                
                # Get best available format
                formats = info.get('formats', [])
                best_format = max(
                    (f for f in formats if f.get('vcodec') != 'none'),
                    key=lambda f: f.get('height', 0) * f.get('fps', 1) if f.get('height') else 0,
                    default={}
                )
                
                # Get audio format if available
                audio_format = next(
                    (f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none'),
                    {}
                )
                
                # Format the info into our standard format
                video_info = {
                    'id': info.get('id'),
                    'title': info.get('title', 'Untitled'),
                    'author': info.get('uploader'),
                    'channel': info.get('channel'),
                    'channel_id': info.get('channel_id'),
                    'duration': info.get('duration'),
                    'upload_date': info.get('upload_date'),
                    'view_count': info.get('view_count'),
                    'like_count': info.get('like_count'),
                    'dislike_count': info.get('dislike_count'),
                    'average_rating': info.get('average_rating'),
                    'categories': info.get('categories', []),
                    'tags': info.get('tags', []),
                    'description': info.get('description'),
                    'thumbnails': info.get('thumbnails', []),
                    'thumbnail': info.get('thumbnail'),
                    'webpage_url': info.get('webpage_url'),
                    'formats': formats,
                    'requested_formats': info.get('requested_formats'),
                    'format': best_format.get('format'),
                    'format_id': best_format.get('format_id'),
                    'ext': best_format.get('ext', 'mp4'),
                    'width': best_format.get('width'),
                    'height': best_format.get('height'),
                    'fps': best_format.get('fps'),
                    'vcodec': best_format.get('vcodec'),
                    'acodec': best_format.get('acodec') or (audio_format.get('acodec') if audio_format else None),
                    'filesize': best_format.get('filesize') or info.get('filesize'),
                    'filesize_approx': info.get('filesize_approx'),
                    'protocol': best_format.get('protocol'),
                    'is_live': info.get('is_live', False),
                    'was_live': info.get('was_live', False),
                    'extractor': info.get('extractor'),
                    'extractor_key': info.get('extractor_key'),
                    'webpage_url_basename': info.get('webpage_url_basename'),
                    'webpage_url_domain': info.get('webpage_url_domain'),
                    'playable_in_embed': info.get('playable_in_embed', True),
                    'availability': info.get('availability'),
                    'chapters': info.get('chapters', []),
                    'subtitles': info.get('subtitles', {}),
                    'automatic_captions': info.get('automatic_captions', {})
                }
                
                logger.info(f"Fetched video info: {video_info.get('title')} ({video_info.get('id')})")
                return video_info
                
        except yt_dlp.DownloadError as e:
            error_msg = f"Error getting video info: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ValueError(f"Failed to get video info: {str(e)}")
        except Exception as e:
            error_msg = f"Unexpected error getting video info: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ValueError(f"An unexpected error occurred: {str(e)}")
    
    def _progress_hook(self, d: Dict[str, Any], request_id: Optional[str] = None) -> None:
        """Progress hook for yt-dlp to track download progress."""
        status = d.get('status', '').lower()
        
        if status == 'downloading':
            percent = d.get('_percent_str', '0%').strip('%')
            speed = d.get('_speed_str', 'N/A')
            eta = d.get('_eta_str', 'N/A')
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded_bytes = d.get('downloaded_bytes', 0)
            
            progress_info = {
                'status': 'downloading',
                'percent': float(percent) if percent.replace('.', '').isdigit() else 0,
                'speed': speed,
                'eta': eta,
                'downloaded_bytes': downloaded_bytes,
                'total_bytes': total_bytes,
                'elapsed': d.get('elapsed', 0),
                'filename': d.get('filename', '').split('/')[-1],
            }
            
            if request_id and request_id in self.active_downloads:
                self.active_downloads[request_id].update(progress_info)
                
            logger.debug(f"Download progress: {percent}% - {speed} - ETA: {eta}")
            
        elif status == 'finished':
            logger.info("Download finished, starting post-processing")
            if request_id and request_id in self.active_downloads:
                self.active_downloads[request_id]['status'] = 'processing'
    
    def _get_download_opts(self, output_path: str, request_id: Optional[str] = None) -> dict:
        """Get download options for yt-dlp."""
        opts = self.ytdl_opts.copy()
        
        # Update output template with the full path
        output_dir = os.path.dirname(output_path)
        filename = os.path.basename(output_path)
        
        # Ensure the output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Configure progress hooks
        progress_hook = lambda d: self._progress_hook(d, request_id)
        
        # Update options with download-specific settings
        opts.update({
            'outtmpl': os.path.join(output_dir, filename),
            'progress_hooks': [progress_hook],
            'noprogress': False,
            'quiet': False,
            'no_warnings': False,
            'writethumbnail': True,
            'writesubtitles': False,
            'writeautomaticsub': False,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        })
        
        return opts
    
    def download_video(
        self, 
        url: str, 
        output_path: Optional[str] = None,
        on_progress_callback: Optional[Callable] = None,
        request_id: Optional[str] = None,
        max_retries: int = 3,
        format_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Download a YouTube video with progress tracking and error handling.
        
        Args:
            url: YouTube video URL
            output_path: Custom output path (optional)
            on_progress_callback: Callback function for progress updates
            request_id: Optional request ID for tracking
            max_retries: Maximum number of retry attempts
            format_id: Optional format ID to download specific format
            
        Returns:
            Dict containing download status and metadata
            
        Raises:
            ValueError: If download fails after max retries
            RuntimeError: If there's an error during download
        """
        if not request_id:
            request_id = f'dl_{int(time.time())}_{os.urandom(4).hex()}'
            
        attempt = 0
        last_error = None
        temp_dir = None
        final_path = None
        
        try:
            # Get video info first
            video_info = self.get_video_info(url)
            video_id = video_info['id']
            video_title = video_info.get('title', 'video')
            
            # Sanitize the title for filename
            safe_title = self._sanitize_filename(video_title)
            
            # Determine output path
            if not output_path:
                output_filename = f"{safe_title}_{video_id}.mp4"
                output_path = str(self.download_dir / output_filename)
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            # Check if file already exists (case-insensitive on case-insensitive filesystems)
            if os.path.exists(output_path):
                logger.info(f"File already exists: {output_path}")
                return {
                    'success': True,
                    'filename': os.path.basename(output_path),
                    'title': video_title,
                    'duration': video_info.get('duration', 0),
                    'path': output_path,
                    'id': video_id,
                    'status': 'completed',
                    'message': 'File already exists'
                }
            
            # Create a temporary directory for downloads
            temp_dir = tempfile.mkdtemp(prefix=f"ytdl_{video_id}_")
            temp_filename = f"{safe_title}_{video_id}.%(ext)s"
            temp_path = os.path.join(temp_dir, temp_filename)
            
            # Initialize download tracking
            if request_id:
                self.active_downloads[request_id] = {
                    'status': 'starting',
                    'percent': 0.0,
                    'speed': '0 B/s',
                    'eta': 'N/A',
                    'downloaded_bytes': 0,
                    'total_bytes': 0,
                    'filename': os.path.basename(output_path),
                    'start_time': time.time(),
                    'url': url,
                    'video_id': video_id,
                    'title': video_title
                }
            
            logger.info(f"Starting download: {url} -> {output_path}")
            
            # Configure download options
            download_opts = self._get_download_opts(temp_path, request_id)
            
            # Override format if specified
            if format_id:
                download_opts['format'] = format_id
            
            # Add post-processor for metadata
            download_opts['postprocessors'].append({
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            })
            
            # Add post-processor for thumbnail embedding if available
            if video_info.get('thumbnail'):
                download_opts['postprocessors'].append({
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': False,
                })
            
            # Retry loop
            while attempt < max_retries:
                try:
                    if request_id in self.active_downloads:
                        self.active_downloads[request_id]['status'] = 'downloading'
                    
                    with yt_dlp.YoutubeDL(download_opts) as ydl:
                        # Start the download
                        ydl.download([url])
                    
                    # If we get here, download was successful
                    break
                    
                except yt_dlp.DownloadError as e:
                    attempt += 1
                    last_error = str(e)
                    wait_time = min(2 ** attempt, 30)  # Exponential backoff, max 30s
                    
                    logger.warning(f"Download attempt {attempt}/{max_retries} failed: {e}")
                    
                    if attempt >= max_retries:
                        raise
                        
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    
            else:  # No break occurred, all retries failed
                raise yt_dlp.DownloadError(f"All {max_retries} download attempts failed. Last error: {last_error}")
            
            # Find the downloaded file
            downloaded_files = [f for f in os.listdir(temp_dir) if f.endswith(('.mp4', '.mkv', '.webm', '.m4a'))]
            
            if not downloaded_files:
                raise FileNotFoundError("No video file found after download")
            
            # Get the main video file (prioritize .mp4)
            video_file = next((f for f in downloaded_files if f.endswith('.mp4')), downloaded_files[0])
            src_path = os.path.join(temp_dir, video_file)
            
            # Determine the final extension (use .mp4 for all video files)
            final_ext = 'mp4' if any(video_file.endswith(ext) for ext in ['.mp4', '.mkv', '.webm']) else video_file.split('.')[-1]
            final_filename = f"{os.path.splitext(os.path.basename(output_path))[0]}.{final_ext}"
            final_path = os.path.join(os.path.dirname(output_path), final_filename)
            
            # Move the file to the final location
            shutil.move(src_path, final_path)
            
            # Clean up any remaining files
            for f in os.listdir(temp_dir):
                try:
                    os.unlink(os.path.join(temp_dir, f))
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file {f}: {e}")
            
            logger.info(f"Successfully downloaded: {final_path}")
            
            # Update active downloads
            if request_id in self.active_downloads:
                self.active_downloads[request_id].update({
                    'status': 'completed',
                    'percent': 100.0,
                    'path': final_path,
                    'filename': os.path.basename(final_path),
                    'end_time': time.time(),
                    'elapsed': time.time() - self.active_downloads[request_id]['start_time']
                })
            
            return {
                'success': True,
                'filename': os.path.basename(final_path),
                'title': video_title,
                'duration': video_info.get('duration', 0),
                'path': final_path,
                'id': video_id,
                'status': 'completed',
                'filesize': os.path.getsize(final_path) if os.path.exists(final_path) else 0,
                'format': video_info.get('format'),
                'format_id': video_info.get('format_id'),
                'ext': final_ext,
                'width': video_info.get('width'),
                'height': video_info.get('height'),
                'fps': video_info.get('fps'),
                'vcodec': video_info.get('vcodec'),
                'acodec': video_info.get('acodec')
            }
            
        except Exception as e:
            error_msg = f"Failed to download video: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Update active downloads with error
            if request_id in self.active_downloads:
                self.active_downloads[request_id].update({
                    'status': 'error',
                    'error': str(e),
                    'end_time': time.time(),
                    'elapsed': time.time() - self.active_downloads[request_id]['start_time']
                })
            
            raise RuntimeError(error_msg) from e
            
        finally:
            # Clean up temporary directory
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary directory {temp_dir}: {e}")
            
            # Clean up active downloads if this was the last reference
            if request_id in self.active_downloads:
                # Only remove if the download is complete or failed
                if self.active_downloads[request_id].get('status') in ['completed', 'error']:
                    del self.active_downloads[request_id]
            
            # If we get here, the download was successful
            return {
                'success': True,
                'filename': os.path.basename(output_path) if output_path else None,
                'title': video_info.get('title', 'Unknown') if video_info else 'Unknown',
                'duration': video_info.get('duration', 0) if video_info else 0,
                'path': output_path
            }
