import os
import sys
import json
import logging
import tempfile
import shutil
import time
import uuid
import re
import subprocess
import signal
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any, Set
from datetime import datetime

from .segment_cutter import cut_segment
from .caption_overlay import add_captions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('renderer.log')
    ]
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_FFMPEG_TIMEOUT = 300  # 5 minutes

# Global set to track processed files
_processed_files = set()

class VideoRenderer:
    def __init__(self, base_dir: Optional[str] = None, temp_dir: Optional[str] = None):
        """Initialize the video renderer with base directories."""
        # Initialize directories and configuration
        if base_dir is None:
            # Try to get BASE_DIR from environment variable, fall back to default
            base_dir = os.environ.get('BASE_DIR')
            if not base_dir:
                base_dir = str(Path(os.getcwd()) / 'data')
                logger.warning(f"BASE_DIR not set in environment, using default: {base_dir}")
            else:
                logger.info(f"Using BASE_DIR from environment: {base_dir}")
        
        self.base_dir = Path(base_dir)
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / 'clip_renderer'
        
        # Create directories if they don't exist
        self.downloads_dir = self.base_dir / 'downloads'
        self.transcripts_dir = self.base_dir / 'transcripts'
        self.clips_dir = self.base_dir / 'clips'
        self.final_dir = self.base_dir / 'final'
        
        # Ensure directories exist
        for d in [self.downloads_dir, self.transcripts_dir, self.clips_dir, self.final_dir, self.temp_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # Initialize FFmpeg path
        self.ffmpeg_path = shutil.which('ffmpeg')
        if not self.ffmpeg_path:
            raise RuntimeError("FFmpeg not found in PATH. Please install FFmpeg.")
        
        logger.info(f"Initialized VideoRenderer with base directory: {self.base_dir}")
        logger.debug(f"Temporary files will be stored in: {self.temp_dir}")
        logger.debug(f"Using FFmpeg at: {self.ffmpeg_path}")

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds as HH:MM:SS."""
        try:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            seconds = int(seconds % 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except (TypeError, ValueError) as e:
            logger.error(f"Error formatting duration {seconds}: {e}")
            return "00:00:00"

    def _get_file_paths(self, video_name: str) -> Tuple[Path, Path, Path]:
        """Get the paths for video, transcript, and clips JSON files."""
        video_path = self.downloads_dir / video_name
        transcript_path = self.transcripts_dir / f"{video_name.rsplit('.', 1)[0]}.json"
        clips_path = self.clips_dir / f"{video_name.rsplit('.', 1)[0]}_clips.json"
        logger.debug(f"Looking for clips file at: {clips_path}")
        return video_path, transcript_path, clips_path

    def render_clips(
        self,
        video_name: str,
        output_dir: Optional[Union[str, Path]] = None,
        format: str = "vertical",
        add_captions: bool = True,
        normalize_audio: bool = True
    ) -> Tuple[bool, List[str], Optional[str]]:
        """
        Render video clips based on the recommended clips from the transcript.
        
        Args:
            video_name: Name of the video file (must be in downloads directory)
            output_dir: Directory to save rendered clips (defaults to final_dir/video_name)
            format: Output format ("vertical", "square", or "original")
            add_captions: Whether to add captions to the output video
            
        Returns:
            Tuple of (success: bool, clips: List[str], error: Optional[str])
            
        Raises:
            FileNotFoundError: If any required input file is not found
        """
        # Get file paths
        video_path, transcript_path, clips_path = self._get_file_paths(video_name)
        
        # Validate files exist - these will raise FileNotFoundError if files are missing
        if not video_path.exists():
            error_msg = f"Video file not found: {video_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
            
        if not transcript_path.exists():
            error_msg = f"Transcript file not found: {transcript_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
            
        if not clips_path.exists():
            error_msg = f"Clips file not found: {clips_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        try:
            # Load clips data
            with open(clips_path, 'r') as f:
                clips_data = json.load(f)
            
            # Create output directory if it doesn't exist
            output_dir = Path(output_dir) if output_dir else self.final_dir / video_name.rsplit('.', 1)[0]
            output_dir.mkdir(parents=True, exist_ok=True)
            
            rendered_clips = []
            
            # Handle both formats: list of clips or dict with 'recommended_clips' key
            if isinstance(clips_data, list):
                # Direct list of clips
                clips = clips_data
            else:
                # Dictionary with 'recommended_clips' key
                clips = clips_data.get('recommended_clips', [])
                
            # Process each recommended clip
            for i, clip in enumerate(clips, 1):
                if isinstance(clip, dict):
                    start_time = clip.get('start', 0)
                    end_time = clip.get('end', 0)
                    text = clip.get('text', '')
                else:
                    # Handle case where clip is a tuple or list [start, end, text]
                    try:
                        start_time = float(clip[0]) if len(clip) > 0 else 0
                        end_time = float(clip[1]) if len(clip) > 1 else 0
                        text = str(clip[2]) if len(clip) > 2 else ''
                    except (IndexError, TypeError, ValueError):
                        logger.warning(f"Invalid clip format: {clip}")
                        continue
                
                if end_time <= start_time:
                    logger.warning(f"Invalid clip times: start={start_time}, end={end_time}")
                    continue
                
                # Generate output filename
                output_path = output_dir / f"{video_name.rsplit('.', 1)[0]}_clip_{i}.mp4"
                
                try:
                    # Cut the segment
                    success, message = cut_segment(
                        input_path=video_path,
                        output_path=output_path,
                        start_time=start_time,
                        end_time=end_time,
                        video_format=format
                    )
                    
                    if not success:
                        logger.error(f"Failed to create clip: {message}")
                        continue
                    
                    # Add captions if requested
                    if add_captions:
                        try:
                            # Import here to avoid circular imports
                            from .caption_overlay import add_captions as _add_captions
                            
                            # Create output path for captioned video
                            captioned_path = output_path.with_stem(f"{output_path.stem}_captioned")
                            
                            # Add captions to the video
                            caption_success, caption_output = _add_captions(
                                video_path=str(output_path),
                                transcript_path=str(transcript_path),
                                output_path=str(captioned_path)
                            )
                            
                            if caption_success and caption_output and os.path.exists(caption_output):
                                # If captions were added successfully, use the captioned version
                                output_path.unlink(missing_ok=True)  # Remove the uncaptioned version
                                output_path = Path(caption_output)
                                logger.info(f"Successfully added captions to {output_path}")
                                
                        except Exception as e:
                            logger.error(f"Failed to add captions: {str(e)}", exc_info=True)
                            continue
                    
                    rendered_clips.append(str(output_path))
                    
                except Exception as e:
                    logger.error(f"Error processing clip {i}: {str(e)}", exc_info=True)
                    continue
            
            if not rendered_clips:
                return False, [], "No clips were successfully rendered"
                
            return True, rendered_clips, None
            
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse clips data: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, [], error_msg
            
        except OSError as e:
            error_msg = f"File system error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, [], error_msg
            
        except Exception as e:
            error_msg = f"Unexpected error rendering clips: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, [], error_msg

# Add any additional utility functions here

def create_renderer(base_dir: Optional[str] = None, temp_dir: Optional[str] = None) -> VideoRenderer:
    """Create and return a configured VideoRenderer instance."""
    return VideoRenderer(base_dir=base_dir, temp_dir=temp_dir)
