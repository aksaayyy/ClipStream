"""
FFmpeg utility functions for the ClipStream renderer.
"""
import os
import json
import subprocess
import logging
import shutil
from pathlib import Path
from typing import Tuple, Optional, List, Union, Dict, Any

# Default timeout for FFmpeg commands (5 minutes)
DEFAULT_FFMPEG_TIMEOUT = 300

# Set up logging
logger = logging.getLogger(__name__)

def run_ffmpeg_command(
    cmd: List[str],
    timeout: int = DEFAULT_FFMPEG_TIMEOUT,
    description: str = "FFmpeg command",
    log_output: bool = True
) -> Tuple[bool, str]:
    """
    Run an FFmpeg command with timeout and error handling.
    
    Args:
        cmd: List of command-line arguments for FFmpeg
        timeout: Maximum execution time in seconds
        description: Description of the command for logging
        log_output: Whether to log the command output
        
    Returns:
        Tuple of (success: bool, output: str)
    """
    logger = logging.getLogger(__name__)
    
    # Convert all arguments to strings
    cmd = [str(arg) for arg in cmd]
    
    # Log the command (without sensitive data)
    safe_cmd = ' '.join(cmd)
    logger.info(f"Running {description}: {safe_cmd}")
    
    try:
        # Run the command with timeout
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=True,
            timeout=timeout
        )
        output = result.stdout
        
        if log_output and output.strip():
            logger.debug(f"{description} output:\n{output}")
            
        return True, output
        
    except subprocess.CalledProcessError as e:
        error_msg = f"{description} failed with code {e.returncode}: {e.output}"
        logger.error(error_msg)
        return False, error_msg
        
    except subprocess.TimeoutExpired:
        error_msg = f"{description} timed out after {timeout} seconds"
        logger.error(error_msg)
        return False, error_msg
        
    except Exception as e:
        error_msg = f"Unexpected error running {description}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

def check_ffmpeg_installed() -> bool:
    """Check if FFmpeg is installed and accessible."""
    try:
        subprocess.run(
            ['ffmpeg', '-version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def get_video_duration(video_path: Union[str, Path]) -> Optional[float]:
    """
    Get the duration of a video file using FFprobe.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Duration in seconds, or None if unable to determine
    """
    try:
        video_path = str(video_path)
        if not os.path.isfile(video_path):
            logger.error(f"Video file not found: {video_path}")
            return None
            
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'json',
            video_path
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        
        data = json.loads(result.stdout)
        return float(data['format']['duration'])
        
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Error getting video duration: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_video_duration: {e}")
        return None


def check_ffmpeg_installed() -> bool:
    """
    Check if FFmpeg is installed and accessible.
    
    Returns:
        bool: True if FFmpeg is installed, False otherwise
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False
