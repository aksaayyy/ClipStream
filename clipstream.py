#!/usr/bin/env python3
"""
ClipStream - YouTube to Viral Shorts Generator

A command-line interface for the ClipStream system.
"""

import os
import sys
import json
import time
import logging
import argparse
import requests
from typing import Optional, Dict, Any
from pathlib import Path
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("clipstream-cli")

# Configuration
DEFAULT_API_URL = "http://localhost:8000"
CONFIG_FILE = os.path.expanduser("~/.clipstream/config.json")

class ClipStreamCLI:
    def __init__(self, api_url: str = None, debug: bool = False):
        """Initialize the CLI with configuration."""
        self.api_url = api_url or self._load_config().get('api_url', DEFAULT_API_URL)
        self.debug = debug
        
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug(f"Debug mode enabled. API URL: {self.api_url}")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
        return {}
    
    def _save_config(self, config: Dict[str, Any]):
        """Save configuration to file."""
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def check_health(self) -> bool:
        """Check if the API is healthy."""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            if response.status_code == 200:
                logger.info(f"✓ Service is healthy: {response.json()}")
                return True
            else:
                logger.error(f"✗ Service unhealthy: {response.text}")
                return False
        except requests.RequestException as e:
            logger.error(f"✗ Failed to connect to {self.api_url}: {e}")
            return False
    
    def _get_video_info(self, url: str) -> Optional[Dict[str, Any]]:
        """Get video information from the API without downloading."""
        try:
            response = requests.get(
                f"{self.api_url}/info",  # Note: This endpoint needs to be implemented in the API
                params={"url": url},
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            return None
        except requests.RequestException as e:
            if self.debug:
                logger.debug(f"Error getting video info: {e}")
            return None
    
    def _get_existing_download(self, title: str) -> Optional[str]:
        """Check if a video with the same title already exists in the downloads directory."""
        try:
            # This assumes the API is running from the project root
            download_dir = os.path.join(os.path.dirname(__file__), "services", "downloads")
            if not os.path.exists(download_dir):
                return None
                
            # Create a safe filename pattern from the title
            safe_title = "".join(c if c.isalnum() or c in ' -_' else '_' for c in title)
            pattern = f"*{safe_title}*.mp4"
            
            import glob
            existing = glob.glob(os.path.join(download_dir, pattern))
            return existing[0] if existing else None
        except Exception as e:
            if self.debug:
                logger.debug(f"Error checking for existing download: {e}")
            return None
    
    def download_video(self, url: str, output_dir: str = None, force: bool = False) -> Optional[Dict[str, Any]]:
        """Download a video from YouTube with enhanced timeout handling."""
        if not self._validate_url(url):
            logger.error("Invalid YouTube URL")
            return None
            
        try:
            # First get video info to check for existing downloads
            try:
                video_info = self._get_video_info(url)
                if not video_info:
                    logger.warning("Could not get video information. Proceeding with download...")
                else:
                    # Check for existing download with the same title
                    existing_file = self._get_existing_download(video_info.get('title', ''))
                    if existing_file and not force:
                        logger.warning(f"⚠️  This video appears to be already downloaded at: {existing_file}")
                        logger.info("Use --force to download again")
                        return None
            except requests.RequestException as e:
                logger.warning(f"Could not check for existing downloads: {e}")
                logger.info("Proceeding with download...")
            
            logger.info(f"⌛ Downloading video from {url}")
            start_time = time.time()
            
            # Create a request payload matching the DownloadRequest model
            payload = {
                "url": url,
                "format": "mp4",
                "request_id": f"cli_{int(time.time())}"  # Add a timestamp-based request ID
            }
            
            if self.debug:
                logger.debug(f"Sending request payload: {payload}")
            
            # Set a very long timeout for large downloads (1 hour)
            timeout = 3600  # 1 hour in seconds
            
            try:
                response = requests.post(
                    f"{self.api_url}/fetch",
                    json=payload,
                    timeout=timeout,
                    headers={"Content-Type": "application/json"},
                    stream=True  # Stream the response to handle large files better
                )
                
                # Check if the request was successful
                response.raise_for_status()
                result = response.json()
                
                elapsed = time.time() - start_time
                
                logger.info(f"✅ Successfully downloaded: {result.get('title')}")
                logger.info(f"   Duration: {result.get('duration')}")
                logger.info(f"   File: {result.get('path')}")
                logger.info(f"   Size: {result.get('size_mb', 'N/A')} MB")
                logger.info(f"   Time taken: {elapsed:.2f} seconds")
                
                return result
                
            except requests.Timeout:
                logger.error("⚠️  Download timed out. The video might be very large or the server is taking too long to respond.")
                logger.info("Try again or use a direct download method for very large videos.")
                return None
                
            except requests.RequestException as e:
                logger.error(f"⚠️  Download failed: {str(e)}")
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_detail = e.response.json().get('detail', 'No details provided')
                        logger.error(f"Server error: {error_detail}")
                    except:
                        logger.error(f"HTTP {e.response.status_code}: {e.response.text}")
                return None
            
        except requests.RequestException as e:
            logger.error(f"Error downloading video: {e}")
            return None
    
    def _validate_url(self, url: str) -> bool:
        """Validate YouTube URL format."""
        try:
            result = urlparse(url)
            return all([result.scheme in ['http', 'https'],
                      'youtube.com' in result.netloc or 'youtu.be' in result.netloc])
        except:
            return False

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='ClipStream - YouTube to Viral Shorts Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''Examples:
  clipstream download https://www.youtube.com/watch?v=dQw4w9WgXcQ
  clipstream --api http://localhost:8000 download https://youtu.be/dQw4w9WgXcQ
  clipstream check-health'''
    )
    
    # Global arguments
    parser.add_argument('--api', type=str, help='API server URL')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    # Subcommands
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # Download command
    dl_parser = subparsers.add_parser('download', help='Download a YouTube video')
    dl_parser.add_argument('url', type=str, help='YouTube video URL')
    dl_parser.add_argument('--output', '-o', type=str, help='Output directory')
    dl_parser.add_argument('--force', '-f', action='store_true', help='Force download even if file exists')
    
    # Health check command
    subparsers.add_parser('check-health', help='Check service health')
    
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()
    
    try:
        cli = ClipStreamCLI(api_url=args.api, debug=args.debug)
        
        if args.command == 'check-health':
            if not cli.check_health():
                sys.exit(1)
                
        elif args.command == 'download':
            if not cli.download_video(args.url, args.output, args.force):
                sys.exit(1)
                
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=args.debug)
        sys.exit(1)

if __name__ == "__main__":
    main()
