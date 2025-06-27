import os
import sys
import json
import logging
import tempfile
import shutil
import time
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable, Any, Union, Set

from .utils.ffmpeg_utils import (
    run_ffmpeg_command,
    DEFAULT_FFMPEG_TIMEOUT,
    check_ffmpeg_installed,
    get_video_duration as get_video_duration_util
)
from .segment_cutter import cut_segment, get_video_duration
from .caption_overlay import add_captions

logger = logging.getLogger(__name__)

# Re-export for backward compatibility
DEFAULT_TIMEOUT = DEFAULT_FFMPEG_TIMEOUT

# Track processed files to prevent duplicate processing
_processed_files: Set[str] = set()

def get_processed_files() -> Set[str]:
    """Get the set of processed file paths."""
    return _processed_files.copy()

def clear_processed_files() -> None:
    """Clear the set of processed file paths."""
    _processed_files.clear()

def mark_file_processed(file_path: Union[str, Path]) -> None:
    """Mark a file as processed."""
    _processed_files.add(str(Path(file_path).resolve()))

def is_file_processed(file_path: Union[str, Path]) -> bool:
    """Check if a file has been processed."""
    return str(Path(file_path).resolve()) in _processed_files


def create_directory(path: Path, description: str = "") -> bool:
    """Safely create a directory with error handling and logging."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created/verified directory: {path} {description}")
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {path}: {e}")
        return False

class VideoRenderer:
    def __init__(self, base_dir: Optional[str] = None, temp_dir: Optional[str] = None):
        """
        Initialize the video renderer with base directories.
        
        Args:
            base_dir: Optional base directory. If not provided, uses BASE_DIR environment variable
                     or defaults to './data' in the current working directory.
            temp_dir: Optional temporary directory. If not provided, uses system temp directory.
        """
        # Set up base directory
        if base_dir is None:
            base_dir = os.environ.get('BASE_DIR')
            if not base_dir:
                base_dir = os.path.join(os.getcwd(), 'data')
                logger.warning(f"BASE_DIR not set, using default: {base_dir}")
        
        self.base_dir = Path(base_dir).resolve()
        
        # Set up temp directory
        self.temp_dir = Path(temp_dir) if temp_dir else Path(tempfile.gettempdir()) / "clip_renderer"
        
        # Define directory structure
        self.downloads_dir = self.base_dir / "downloads"
        self.transcripts_dir = self.base_dir / "transcripts"
        self.clips_dir = self.base_dir / "clips"
        self.final_dir = self.base_dir / "final"
        
        # FFmpeg configuration
        self.ffmpeg_path = shutil.which('ffmpeg')
        if not self.ffmpeg_path:
            raise RuntimeError("FFmpeg not found in PATH. Please install FFmpeg and ensure it's available in your system PATH.")
        
        # Log FFmpeg version
        self._log_ffmpeg_version()
        
        logger.info(f"Initializing VideoRenderer with base directory: {self.base_dir}")
        logger.debug(f"Temporary files will be stored in: {self.temp_dir}")
        logger.debug(f"Using FFmpeg at: {self.ffmpeg_path}")
        
        # Create all required directories
        self._setup_directories()
    
    def _log_ffmpeg_version(self) -> None:
        """Log the FFmpeg version being used."""
        if not check_ffmpeg_installed():
            logger.error("FFmpeg is not installed or not in PATH")
            return
            
        success, output = run_ffmpeg_command(
            ['ffmpeg', '-version'],
            description="Get FFmpeg version"
        )
        
        if success and output:
            version_line = output.split('\n')[0]
            logger.info(f"FFmpeg version: {version_line}")
        else:
            logger.warning("Failed to get FFmpeg version")
    
    def _build_ffmpeg_base_cmd(self) -> List[str]:
        """Build the base FFmpeg command with common options."""
        return [
            self.ffmpeg_path,
            '-y',  # Overwrite output files without asking
            '-nostdin',  # Disable interaction on standard input
            '-loglevel', 'info',  # Set log level to info
            '-hide_banner',  # Hide banner
            '-stats',  # Show encoding progress
        ]
    
    def _build_ffmpeg_input_args(self, input_file: Path) -> List[str]:
        """Build FFmpeg input arguments."""
        return [
            '-i', str(input_file)
        ]
    
    def _build_ffmpeg_output_args(
        self, 
        output_file: Path, 
        video_codec: str = 'libx264',
        audio_codec: str = 'aac',
        preset: str = 'fast',
        crf: int = 23
    ) -> List[str]:
        """Build FFmpeg output arguments."""
        return [
            '-c:v', video_codec,
            '-preset', preset,
            '-crf', str(crf),
            '-movflags', '+faststart',
            '-c:a', audio_codec,
            '-b:a', '192k',
            '-y',  # Overwrite output file
            str(output_file)
        ]
    
    def _run_ffmpeg_command(
        self, 
        input_file: Union[str, Path], 
        output_file: Union[str, Path],
        filters: Optional[List[str]] = None,
        extra_args: Optional[List[str]] = None,
        timeout: int = DEFAULT_FFMPEG_TIMEOUT,
        description: str = "FFmpeg command",
        log_output: bool = True
    ) -> Tuple[bool, str]:
        """
        Run an FFmpeg command with the given parameters.
        
        Args:
            input_file: Path to the input file
            output_file: Path to the output file
            filters: List of filter strings to apply
            extra_args: Additional FFmpeg arguments
            timeout: Maximum time to wait for the command to complete (in seconds)
            description: Description of the command for logging
            log_output: Whether to log the command output
            
        Returns:
            Tuple of (success: bool, output: str)
        """
        # Convert Path objects to strings
        input_file = str(input_file)
        output_file = str(output_file)
        
        # Build the base command
        cmd = ['ffmpeg', '-y', '-i', input_file]
        
        # Add filters if provided
        if filters:
            filter_str = ','.join(str(f) for f in filters if f)
            if filter_str:
                cmd.extend(['-vf', filter_str])
        
        # Add extra arguments if provided
        if extra_args:
            cmd.extend(str(arg) for arg in extra_args)
        
        # Add output file
        cmd.append(output_file)
        
        # Run the command
        success, output = run_ffmpeg_command(
            cmd,
            timeout=timeout,
            description=description,
            log_output=log_output
        )
        
        # Verify output file was created
        if success and not os.path.exists(output_file):
            error_msg = f"Output file was not created: {output_file}"
            logger.error(error_msg)
            return False, error_msg
            
        return success, output
        
        Args:
            input_file: Input video file
            output_file: Output video file
            filters: List of filter strings to apply
            extra_args: Additional FFmpeg arguments
            timeout: Command timeout in seconds
            description: Description for logging
            
        Returns:
            Tuple of (success: bool, output: str)
        """
        # Build the command
        cmd = self._build_ffmpeg_base_cmd()
        cmd.extend(self._build_ffmpeg_input_args(input_file))
        
        # Add filters if provided
        if filters:
            cmd.extend(['-filter_complex', ';'.join(filters)])
        
        # Add extra arguments if provided
        if extra_args:
            cmd.extend(extra_args)
        
        # Add output arguments
        cmd.extend(self._build_ffmpeg_output_args(output_file))
        
        # Run the command
        return run_ffmpeg_command(cmd, timeout=timeout, description=description)
        
    def _setup_directories(self) -> None:
        """Create all required directories with proper error handling."""
        required_dirs = [
            (self.base_dir, "base directory"),
            (self.downloads_dir, "downloads directory"),
            (self.transcripts_dir, "transcripts directory"),
            (self.clips_dir, "clips directory"),
            (self.final_dir, "final output directory"),
            (self.temp_dir, "temporary files directory")
        ]
        
        for directory, desc in required_dirs:
            if not create_directory(directory, desc):
                raise RuntimeError(f"Failed to initialize required {desc}: {directory}")
                
    def _get_temp_file(self, prefix: str = "", suffix: str = "") -> Path:
        """Get a temporary file path with the given prefix and suffix."""
        return self.temp_dir / f"{prefix}{os.urandom(8).hex()}{suffix}"
        
    def cleanup(self) -> None:
        """Clean up temporary files and directories."""
        try:
            if self.temp_dir.exists() and self.temp_dir.is_dir():
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary directory: {e}")
            
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            logger.error(f"Exception in VideoRenderer context: {exc_type.__name__}: {exc_val}", 
                        exc_info=(exc_type, exc_val, exc_tb))
        self.cleanup()
    
    def render_clips(
        self,
        video_name: str,
        format: str = "vertical",
        add_captions: bool = True,
        normalize_audio: bool = True,
        output_dir: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        **kwargs  # Additional FFmpeg options
    ) -> Tuple[bool, List[str], Optional[str]]:
        """
        Render video clips with optional captions and audio normalization.
        
        Args:
            video_name: Name of the video file (e.g., 'video.mp4')
            format: Output format ('vertical', 'square', 'original')
            add_captions: Whether to add captions to the video
            normalize_audio: Whether to normalize audio levels
            output_dir: Custom output directory (defaults to /data/final)
            progress_callback: Optional callback for progress updates
            **kwargs: Additional FFmpeg options
            
        Returns:
            Tuple of (success: bool, output_paths: List[str], error: Optional[str])
        """
        # Log renderer configuration
        logger.info("=" * 80)
        logger.info(f"Starting render_clips with parameters:")
        logger.info(f"- Video: {video_name}")
        logger.info(f"- Format: {format}")
        logger.info(f"- Add captions: {add_captions}")
        logger.info(f"- Normalize audio: {normalize_audio}")
        logger.info(f"- Output dir: {output_dir}")
        logger.info("=" * 80)
        
        # Log environment information
        logger.debug(f"Python executable: {sys.executable}")
        logger.debug(f"Working directory: {os.getcwd()}")
        logger.debug(f"Environment variables: {os.environ.get('FFREPORT', 'Not set')}")
        
        # Log FFmpeg version
        try:
            ffmpeg_version = subprocess.run(
                ['ffmpeg', '-version'], 
                capture_output=True, 
                text=True
            ).stdout.split('\n')[0]
            logger.info(f"FFmpeg version: {ffmpeg_version}")
        except Exception as e:
            logger.warning(f"Could not determine FFmpeg version: {e}")
        
        # Set up paths with validation
        video_path = self.downloads_dir / video_name
        base_name = video_path.stem
        transcript_path = self.transcripts_dir / f"{base_name}.json"
        clips_config_path = self.clips_dir / f"{base_name}_clips.json"
        output_dir = Path(output_dir) if output_dir else self.final_dir
        
        logger.info("=" * 80)
        logger.info("File paths:")
        logger.info(f"- Video: {video_path} (exists: {video_path.exists()})")
        logger.info(f"- Transcript: {transcript_path} (exists: {transcript_path.exists()})")
        logger.info(f"- Clips config: {clips_config_path} (exists: {clips_config_path.exists()})")
        logger.info(f"- Output dir: {output_dir}")
        logger.info("=" * 80)
        
        logger.debug(f"Input paths:")
        logger.debug(f"- Video: {video_path}")
        logger.debug(f"- Transcript: {transcript_path}")
        logger.debug(f"- Clips config: {clips_config_path}")
        logger.debug(f"- Output dir: {output_dir}")
        
        try:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured output directory exists: {output_dir}")
            
            # Validate input files
            for path in [video_path, transcript_path, clips_config_path]:
                if not path.exists():
                    return False, [], f"Input file not found: {path}"
            
            # Load clip configuration
            with open(clips_config_path, 'r', encoding='utf-8') as f:
                clips_config = json.load(f)
            
            rendered_clips = []
            
            # Process each recommended clip
            recommended_clips = clips_config.get('recommended_clips', [])
            logger.info(f"Found {len(recommended_clips)} recommended clips to process")
            
            for i, clip in enumerate(recommended_clips, 1):
                start_time = clip.get('start', 0)
                end_time = clip.get('end', 0)
                clip_duration = end_time - start_time
                
                logger.info(f"\nProcessing clip {i}/{len(recommended_clips)}: "
                            f"{start_time:.2f}s to {end_time:.2f}s ({clip_duration:.2f}s)")
                
                if end_time <= start_time:
                    error_msg = f"Invalid clip times: start={start_time}, end={end_time}"
                    logger.error(error_msg)
                    continue
                
                # Generate output filename
                output_path = output_dir / f"{base_name}_clip_{i}.mp4"
                
                # Create a temporary file for the cut segment
                with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_cut:
                    temp_cut_path = temp_cut.name
                    
                logger.info(f"Processing clip {i}: {start_time:.2f}s to {end_time:.2f}s")
                logger.debug(f"Using temp file: {temp_cut_path}")
                logger.debug(f"Output will be saved to: {output_path}")
                
                try:
                    # Step 1: Cut and format the segment
                    logger.info(f"Cutting segment from {start_time:.2f}s to {end_time:.2f}s")
                    start_time_cut = time.time()
                    success, message = cut_segment(
                        input_path=str(video_path),
                        output_path=temp_cut_path,
                        start_time=start_time,
                        end_time=end_time,
                        video_format=format,
                        normalize_audio=normalize_audio,
                    )
                    cut_duration = time.time() - start_time_cut
                    logger.info(f"Segment cut completed in {cut_duration:.2f}s")
                    if not success:
                        logger.error(f"Failed to cut segment: {message}")
                        continue
                    
                    # Step 2: Add captions if requested
                    if add_captions:
                        logger.info("Adding captions to segment")
                        start_time_captions = time.time()
                        success, message = add_captions(
                            input_path=temp_cut_path,
                            output_path=str(output_path),
                            transcript_path=str(transcript_path),
                            start_time=start_time,
                            end_time=end_time
                        )
                        captions_duration = time.time() - start_time_captions
                        logger.info(f"Captions added in {captions_duration:.2f}s")
                    else:
                        # Just move the file if no captions needed
                        logger.info("Skipping captions as requested")
                        os.rename(temp_cut_path, output_path)
                        success, message = True, "Clip created without captions"
                    
                    if success:
                        rendered_clips.append(str(output_path))
                        clip_info = f"Successfully rendered clip {i}: {output_path}"
                        logger.info(clip_info)
                        
                        # Log file stats
                        if os.path.exists(output_path):
                            size_mb = os.path.getsize(output_path) / (1024 * 1024)
                            duration = self.get_video_duration(output_path)
                            logger.info(f"Clip stats - Size: {size_mb:.2f}MB, Duration: {duration:.2f}s")
                        
                        if progress_callback:
                            progress_callback(i / len(clips_config.get('recommended_clips', [])), f"Clip {i} rendered")
                    else:
                        error_msg = f"Failed to process clip {i}: {message}"
                        logger.error(error_msg)
                        
                except Exception as e:
                    logger.error(f"Error processing clip {i}: {str(e)}", exc_info=True)
                finally:
                    # Clean up temporary files
                    if os.path.exists(temp_cut_path):
                        os.unlink(temp_cut_path)
            
            if not rendered_clips:
                return False, [], "No clips were successfully rendered"
                
            return True, rendered_clips, None
            
        except Exception as e:
            error_msg = f"Error in render_clips: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, [], error_msg
    
    def get_video_info(self, video_name: str) -> Dict:
        """
        Get information about a video file.
        
        Args:
            video_name: Name of the video file
            
        Returns:
            Dictionary containing video information or error message
        """
        video_path = self.downloads_dir / video_name
        if not video_path.exists():
            return {"error": f"Video not found: {video_name}"}
        
        duration = get_video_duration(str(video_path))
        
        return {
            "filename": video_name,
            "path": str(video_path),
            "duration": duration,
            "duration_formatted": self._format_duration(duration) if duration else "Unknown"
        }
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds as HH:MM:SS.
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Formatted duration string (HH:MM:SS)
        """
        try:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            seconds = int(seconds % 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except (TypeError, ValueError) as e:
            logger.error(f"Error formatting duration {seconds}: {e}")
            return "00:00:00"
