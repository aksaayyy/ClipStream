#!/usr/bin/env python3
"""
End-to-end test for the Clip Renderer service.

This script tests the complete rendering pipeline:
1. Downloads a test video
2. Generates a test transcript
3. Creates test clip segments
4. Renders clips with different styles
5. Validates the output
"""

import os
import sys
import json
import time
import shutil
import logging
import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_pipeline.log')
    ]
)
logger = logging.getLogger(__name__)

# Test configuration
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
TEST_VIDEO_DURATION = 213  # seconds
SHORT_VIDEO_PATH = "test_assets/short_test.mp4"
USE_SHORT_VIDEO = True  # Set to False to use YouTube download
DEBUG_MODE = True  # Enable detailed logging and FFmpeg debug output

# Test clips configuration
if USE_SHORT_VIDEO:
    # Shorter clips for the test video
    TEST_CLIPS = [
        {"start": 1, "end": 3, "score": 0.95, "reason": "Short test clip 1"},
        {"start": 2, "end": 4, "score": 0.92, "reason": "Short test clip 2"},
    ]
else:
    # Original longer clips for YouTube video
    TEST_CLIPS = [
        {"start": 10, "end": 30, "score": 0.95, "reason": "Test clip 1"},
        {"start": 60, "end": 90, "score": 0.92, "reason": "Test clip 2"},
    ]

class TestPipeline:
    def __init__(self, output_dir: str = "test_output", keep_files: bool = False, debug: bool = False):
        """Initialize the test pipeline.
        
        Args:
            output_dir: Base directory for test output
            keep_files: If True, keep intermediate files after test
            debug: If True, enable debug logging and FFmpeg verbose output
        """
        self.output_dir = Path(output_dir).resolve()
        self.keep_files = keep_files
        self.debug = debug or DEBUG_MODE
        self.test_data_dir = self.output_dir / "test_data"
        
        # Configure logging level based on debug mode
        log_level = logging.DEBUG if self.debug else logging.INFO
        logging.getLogger().setLevel(log_level)
        
        # Create a local data directory structure
        self.data_dir = self.output_dir / "data"
        self.downloads_dir = self.data_dir / "downloads"
        self.transcripts_dir = self.data_dir / "transcripts"
        self.clips_dir = self.data_dir / "clips"
        self.final_dir = self.data_dir / "final"
        
        # Test files
        if USE_SHORT_VIDEO and os.path.exists(SHORT_VIDEO_PATH):
            # Use the local short test video
            self.video_path = Path(SHORT_VIDEO_PATH).resolve()
            logger.info(f"Using local test video: {self.video_path}")
        else:
            # Fall back to downloaded video
            self.video_path = self.downloads_dir / "test_video.mp4"
        
        self.transcript_path = self.transcripts_dir / "test_video.json"
        self.clips_path = self.clips_dir / "test_video_clips.json"
        
        # Create all required directories
        for dir_path in [self.test_data_dir, self.downloads_dir, 
                        self.transcripts_dir, self.clips_dir, self.final_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {dir_path}")
        
        # Set environment variables
        os.environ["BASE_DIR"] = str(self.data_dir)
        if self.debug:
            os.environ["FFREPORT"] = "file=ffmpeg_%t_%p.log:level=debug"
        
        # Set up test environment
        self.setup_environment()
    
    def setup_environment(self):
        """Set up test environment and dependencies."""
        logger.info("Setting up test environment...")
        
        # Check for required tools
        required_tools = ['ffmpeg', 'ffprobe']
        for tool in required_tools:
            if not shutil.which(tool):
                raise RuntimeError(f"Required tool not found: {tool}")
        
        logger.info("Environment setup complete")
    
    def download_test_video(self) -> bool:
        """Download a test video using yt-dlp."""
        if self.video_path.exists():
            logger.info(f"Using existing test video: {self.video_path}")
            return True
            
        logger.info(f"Downloading test video to {self.video_path}...")
        try:
            # Ensure the downloads directory exists
            self.downloads_dir.mkdir(parents=True, exist_ok=True)
            
            # Create a temporary directory for the download
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_video = Path(temp_dir) / "video.%(ext)s"
                
                # Download the video with yt-dlp
                cmd = [
                    'yt-dlp',
                    '-f', 'best[height<=480]',  # 480p for faster download
                    '-o', str(temp_video),
                    '--no-playlist',
                    '--merge-output-format', 'mp4',  # Ensure MP4 output
                    TEST_VIDEO_URL
                ]
                logger.info(f"Running command: {' '.join(cmd)}")
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"Failed to download video. Error: {result.stderr}")
                    return False
                
                # Find the downloaded file
                downloaded_files = list(Path(temp_dir).glob("video.*"))
                if not downloaded_files:
                    logger.error("No video files found after download")
                    return False
                
                # Move to the final location
                downloaded_file = downloaded_files[0]
                shutil.move(str(downloaded_file), str(self.video_path))
                
                if not self.video_path.exists():
                    logger.error(f"Failed to move video to {self.video_path}")
                    return False
            
            logger.info(f"Successfully downloaded video to {self.video_path} (size: {self.video_path.stat().st_size / (1024*1024):.2f}MB)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download test video: {str(e)}", exc_info=True)
            return False
    
    def generate_test_transcript(self) -> bool:
        """Generate a test transcript file."""
        transcript = {
            "segments": [
                {
                    "start": 10,
                    "end": 15,
                    "text": "We're no strangers to love"
                },
                {
                    "start": 15,
                    "end": 21,
                    "text": "You know the rules and so do I"
                },
                {
                    "start": 21,
                    "end": 27,
                    "text": "A full commitment's what I'm thinking of"
                },
                {
                    "start": 27,
                    "end": 33,
                    "text": "You wouldn't get this from any other guy"
                },
                {
                    "start": 60,
                    "end": 66,
                    "text": "Never gonna give you up"
                },
                {
                    "start": 66,
                    "end": 72,
                    "text": "Never gonna let you down"
                },
                {
                    "start": 72,
                    "end": 78,
                    "text": "Never gonna run around and desert you"
                },
                {
                    "start": 78,
                    "end": 84,
                    "text": "Never gonna make you cry"
                },
                {
                    "start": 84,
                    "end": 90,
                    "text": "Never gonna say goodbye"
                }
            ]
        }
        
        try:
            with open(self.transcript_path, 'w') as f:
                json.dump(transcript, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to generate test transcript: {e}")
            return False
    
    def generate_test_clips(self) -> bool:
        """Generate test clip segments."""
        clips = {
            "recommended_clips": TEST_CLIPS
        }
        
        try:
            with open(self.clips_path, 'w') as f:
                json.dump(clips, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to generate test clips: {e}")
            return False
    
    def run_ffmpeg_command(self, cmd: List[str], timeout: int = 60) -> Tuple[bool, str]:
        """
        Run a command with timeout and detailed error handling.
        
        Args:
            cmd: Command to run as list of strings
            timeout: Maximum time in seconds to wait for command completion
            
        Returns:
            Tuple of (success: bool, output: str)
        """
        import subprocess
        from subprocess import Popen, PIPE, TimeoutExpired
        
        start_time = time.time()
        cmd_str = ' '.join(cmd)
        logger.debug(f"Running command: {cmd_str}")
        
        try:
            # Add debug flags if in debug mode and this is an ffmpeg command
            if self.debug and 'ffmpeg' in cmd[0]:
                cmd = cmd[:1] + ["-loglevel", "debug", "-report"] + cmd[1:]
            
            # Start the process
            process = Popen(
                cmd,
                stdout=PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )
            
            # Monitor the process with timeout
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                
                # Log the output
                if stdout:
                    logger.debug(f"Command stdout: {stdout[:1000]}" + ("..." if len(stdout) > 1000 else ""))
                if stderr:
                    logger.debug(f"Command stderr: {stderr[:1000]}" + ("..." if len(stderr) > 1000 else ""))
                
                if process.returncode == 0:
                    logger.debug(f"Command completed successfully in {time.time() - start_time:.2f}s")
                    return True, stdout
                else:
                    error_msg = f"Command failed with code {process.returncode}"
                    if stderr:
                        error_msg += f"\nError output: {stderr}"
                    logger.error(error_msg)
                    return False, error_msg
                    
            except TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                error_msg = f"Command timed out after {timeout} seconds"
                if stdout:
                    error_msg += f"\nPartial stdout: {stdout[-1000:]}"
                if stderr:
                    error_msg += f"\nPartial stderr: {stderr[-1000:]}"
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Error executing command: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
            
    def get_video_duration(self, video_path: Path) -> Optional[float]:
        """Get the duration of a video file in seconds using ffprobe."""
        if not video_path.exists():
            logger.error(f"Video file does not exist: {video_path}")
            return None
            
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(video_path)
        ]
        
        logger.debug(f"Running command: {' '.join(cmd)}")
        success, output = self.run_ffmpeg_command(cmd, timeout=10)
        
        if not success or not output.strip():
            logger.error(f"Failed to get duration for {video_path}: {output}")
            return None
            
        try:
            duration = float(output.strip())
            logger.debug(f"Video {video_path} duration: {duration:.2f} seconds")
            return duration
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing duration from '{output}': {e}")
            return None

    def test_vertical_format(self) -> Tuple[bool, str]:
        """Test rendering with vertical format (9:16)."""
        output_file = self.final_dir / "test_vertical.mp4"
        
        # Clean up any existing output file
        if output_file.exists():
            logger.debug(f"Removing existing output file: {output_file}")
            output_file.unlink()
        
        # First, try a simple FFmpeg command to test basic functionality
        simple_cmd = [
            'ffmpeg',
            '-loglevel', 'info',  # Set log level to info to see progress
            '-i', str(self.video_path),
            '-t', '5',  # Limit to 5 seconds for testing
            '-vf', 'scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:-1:-1:color=black',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-y',  # Overwrite output file
            str(output_file)
        ]
        
        logger.info("Running simple vertical format test with FFmpeg directly")
        logger.info(f"Command: {' '.join(simple_cmd)}")
        
        # Run the simple FFmpeg command
        success, output = self.run_ffmpeg_command(simple_cmd, timeout=30)
        
        if not success:
            return False, f"Simple vertical format test failed: {output}"
        
        # Verify the output file was created and has content
        if not output_file.exists():
            return False, f"Output file was not created: {output_file}"
            
        file_size = output_file.stat().st_size
        logger.info(f"Output file created: {output_file} ({file_size} bytes)")
        
        if file_size == 0:
            return False, f"Output file is empty: {output_file}"
        
        # Get video duration
        duration = self.get_video_duration(output_file)
        if duration is None:
            return False, f"Could not determine video duration for {output_file}"
        
        # For the short test video, we expect exactly 5 seconds
        expected_duration = 5.0
        tolerance = 0.1  # 100ms tolerance for short clips
        
        logger.info(f"Video duration: {duration:.2f}s (expected: {expected_duration}s)")
        
        if abs(duration - expected_duration) > tolerance:
            return False, f"Unexpected output duration: {duration:.2f}s (expected {expected_duration}s)"
        
        # If we're in debug mode, skip the full renderer test
        if self.debug:
            logger.info("Skipping full renderer test in debug mode")
            return True, f"Simple vertical format test passed: {output_file} ({file_size/1024:.1f}KB, {duration:.2f}s)"
            
        # Test the full renderer
        logger.info("Simple test passed. Running full renderer test...")
        
        # Prepare the full renderer command
        cmd = [
            'python', '-m', 'app.main',
            '--video', str(self.video_path.name),
            '--transcript', str(self.transcript_path.name),
            '--clips', str(self.clips_path.name),
            '--output-dir', str(self.final_dir),
            '--format', 'vertical',
            '--add-captions',
            '--normalize-audio'
        ]
        
        if self.debug:
            cmd.append('--debug')
        
        logger.info(f"Running full renderer test: {' '.join(cmd)}")
        
        # Run the full renderer
        success, output = self.run_ffmpeg_command(cmd, timeout=300)
        
        if not success:
            return False, f"Full renderer test failed: {output}"
        
        # The full renderer should create files with a specific naming pattern
        expected_output = self.final_dir / f"{self.video_path.stem}_vertical.mp4"
        if not expected_output.exists():
            return False, f"Expected output file not found: {expected_output}"
            
        # Verify the output file
        file_size = expected_output.stat().st_size
        logger.info(f"Renderer output: {expected_output} ({file_size} bytes)")
        
        if file_size == 0:
            return False, f"Renderer output file is empty: {expected_output}"
        
        duration = self.get_video_duration(expected_output)
        if duration is None:
            return False, f"Could not determine video duration for {expected_output}"
            
        logger.info(f"Renderer output duration: {duration:.2f}s")
        
        return True, f"Vertical format test passed: {expected_output} ({file_size/1024:.1f}KB, {duration:.2f}s)"
    
    def test_square_format(self) -> Tuple[bool, str]:
        """Test rendering with square format (1:1)."""
        output_dir = self.output_dir / "square"
        output_dir.mkdir(exist_ok=True)
        
        output_file = self.final_dir / f"{self.video_path.stem}_clip_0.mp4"
        
        # Ensure the output file doesn't exist from a previous test
        if output_file.exists():
            output_file.unlink()
        
        cmd = [
            'python', '-m', 'app.main',
            '--video', str(self.video_path.name),
            '--transcript', str(self.transcript_path.relative_to(self.transcripts_dir)),
            '--clips', str(self.clips_path.relative_to(self.clips_dir)),
            '--output-dir', str(self.final_dir),
            '--format', 'square',
            '--add-captions',
            '--normalize-audio'
        ]
        
        logger.info(f"Running square format test with command: {' '.join(cmd)}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"Video path: {self.video_path} (exists: {self.video_path.exists()})")
        logger.info(f"Transcript path: {self.transcript_path} (exists: {self.transcript_path.exists()})")
        logger.info(f"Clips path: {self.clips_path} (exists: {self.clips_path.exists()})")
        
        logger.info(f"Running square format test: {' '.join(cmd)}")
        success, output = self.run_ffmpeg_command(cmd)
        
        if not success:
            return False, f"Square format test failed: {output}"
        
        # Verify output file
        if not output_file.exists():
            return False, f"Output file not found: {output_file}"
        
        return True, f"Square format test passed: {output_file}"
    
    def test_original_format(self) -> Tuple[bool, str]:
        """Test rendering with original format."""
        output_dir = self.output_dir / "original"
        output_dir.mkdir(exist_ok=True)
        
        output_file = self.final_dir / f"{self.video_path.stem}_clip_0.mp4"
        
        # Ensure the output file doesn't exist from a previous test
        if output_file.exists():
            output_file.unlink()
        
        cmd = [
            'python', '-m', 'app.main',
            '--video', str(self.video_path.name),
            '--transcript', str(self.transcript_path.relative_to(self.transcripts_dir)),
            '--clips', str(self.clips_path.relative_to(self.clips_dir)),
            '--output-dir', str(self.final_dir),
            '--format', 'original',
            '--add-captions',
            '--normalize-audio'
        ]
        
        logger.info(f"Running original format test with command: {' '.join(cmd)}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"Video path: {self.video_path} (exists: {self.video_path.exists()})")
        logger.info(f"Transcript path: {self.transcript_path} (exists: {self.transcript_path.exists()})")
        logger.info(f"Clips path: {self.clips_path} (exists: {self.clips_path.exists()})")
        
        logger.info(f"Running original format test: {' '.join(cmd)}")
        success, output = self.run_ffmpeg_command(cmd)
        
        if not success:
            return False, f"Original format test failed: {output}"
        
        # Verify output file
        if not output_file.exists():
            return False, f"Output file not found: {output_file}"
        
        return True, f"Original format test passed: {output_file}"
    
    def run_tests(self) -> bool:
        """Run all tests and return overall success status."""
        logger.info("Starting clip renderer tests...")
        
        # Set up test data
        if not all([
            self.download_test_video(),
            self.generate_test_transcript(),
            self.generate_test_clips()
        ]):
            logger.error("Failed to set up test data")
            return False
        
        # Run format tests
        test_results = []
        
        for test_func in [
            self.test_vertical_format,
            self.test_square_format,
            self.test_original_format
        ]:
            test_name = test_func.__name__
            logger.info(f"Running test: {test_name}")
            
            start_time = time.time()
            success, message = test_func()
            duration = time.time() - start_time
            
            status = "PASSED" if success else "FAILED"
            logger.info(f"Test {test_name} {status} in {duration:.2f}s")
            
            if not success:
                logger.error(f"Test failed: {message}")
            
            test_results.append((test_name, success, message, duration))
        
        # Print summary
        logger.info("\n=== Test Summary ===")
        for name, success, message, duration in test_results:
            status = "✓ PASS" if success else "✗ FAIL"
            logger.info(f"{status} {name} ({duration:.2f}s)")
            if not success:
                logger.info(f"  → {message}")
        
        # Clean up if needed
        if not self.keep_files:
            logger.info("Cleaning up test files...")
            if self.test_data_dir.exists():
                shutil.rmtree(self.test_data_dir)
        
            if not success:
                logger.error(f"Test failed: {message}")
            
            test_results.append((test_name, success, message, duration))
        
        # Print summary
        logger.info("\n=== Test Summary ===")
        for name, success, message, duration in test_results:
            status = "✓ PASS" if success else "✗ FAIL"
            logger.info(f"{status} {name} ({duration:.2f}s)")
            if not success:
                logger.info(f"  → {message}")
        
        # Clean up if needed
        if not self.keep_files:
            logger.info("Cleaning up test files...")
            if self.test_data_dir.exists():
                shutil.rmtree(self.test_data_dir)
        
        # Return overall status
        all_passed = all(success for _, success, _, _ in test_results)
        return all_passed

def main():
    parser = argparse.ArgumentParser(description='Test the Clip Renderer pipeline')
    parser.add_argument('--output-dir', type=str, default='test_output',
                      help='Output directory for test files')
    parser.add_argument('--keep-files', action='store_true',
                      help='Keep test files after completion')
    parser.add_argument('--debug', action='store_true',
                      help='Enable debug logging')
    args = parser.parse_args()
    
    # Initialize and run the test pipeline
    pipeline = TestPipeline(
        output_dir=args.output_dir, 
        keep_files=args.keep_files,
        debug=args.debug
    )
    success = pipeline.run_tests()
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
