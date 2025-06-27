#!/usr/bin/env python3
"""
Enhanced end-to-end test for the Clip Renderer service.

This version includes better error handling, timeouts, and debugging.
"""

import os
import sys
import json
import time
import shutil
import signal
import logging
import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Callable
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)-8s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_pipeline_enhanced.log')
    ]
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_TIMEOUT = 300  # 5 minutes
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
SHORT_VIDEO_PATH = "test_assets/short_test.mp4"
USE_SHORT_VIDEO = True

class TimeoutError(Exception):
    """Custom timeout exception."""
    pass

def run_command(
    cmd: List[str],
    timeout: int = DEFAULT_TIMEOUT,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    log_output: bool = True
) -> Tuple[bool, str]:
    """Run a command with timeout and proper error handling."""
    start_time = time.time()
    cmd_str = ' '.join(cmd)
    
    logger.debug(f"Running command: {cmd_str}")
    logger.debug(f"Working directory: {cwd or os.getcwd()}")
    
    try:
        # Create log file for command output
        with tempfile.NamedTemporaryFile(delete=False, suffix='.log') as log_file:
            log_path = log_file.name
        
        # Run the command
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            env=env or os.environ,
            bufsize=1,
            universal_newlines=True
        )
        
        # Monitor the process
        try:
            stdout, _ = process.communicate(timeout=timeout)
            
            # Write output to log file
            with open(log_path, 'w') as f:
                f.write(f"Command: {cmd_str}\n")
                f.write(f"Working directory: {cwd or os.getcwd()}\n")
                f.write(f"Exit code: {process.returncode}\n")
                f.write("=" * 80 + "\n")
                f.write(stdout)
            
            if log_output:
                logger.debug(f"Command output saved to: {log_path}")
            
            if process.returncode == 0:
                logger.debug(f"Command completed successfully in {time.time() - start_time:.2f}s")
                return True, stdout
            else:
                error_msg = f"Command failed with code {process.returncode}\nSee log: {log_path}"
                logger.error(error_msg)
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            # Terminate the process group to ensure all child processes are killed
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            
            error_msg = f"Command timed out after {timeout} seconds\nSee log: {log_path}"
            logger.error(error_msg)
            return False, error_msg
            
    except Exception as e:
        error_msg = f"Error running command: {str(e)}\nCommand: {cmd_str}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg

class TestPipeline:
    def __init__(self, output_dir: str = "test_output", debug: bool = False):
        """Initialize the test pipeline."""
        self.start_time = time.time()
        self.output_dir = Path(output_dir).resolve()
        self.debug = debug
        
        # Set up logging level
        log_level = logging.DEBUG if self.debug else logging.INFO
        logging.getLogger().setLevel(log_level)
        
        # Set up directories
        self.setup_directories()
        
        # Set up environment
        self.setup_environment()
        
        logger.info(f"Test pipeline initialized in {self.output_dir}")
    
    def log_phase(self, phase: str):
        """Log the start/end of a test phase."""
        elapsed = time.time() - self.start_time
        logger.info(f"{'='*10} {phase} (elapsed: {elapsed:.1f}s) {'='*10}")
    
    def setup_directories(self):
        """Set up test directories."""
        self.data_dir = self.output_dir / "data"
        self.downloads_dir = self.data_dir / "downloads"
        self.transcripts_dir = self.data_dir / "transcripts"
        self.clips_dir = self.data_dir / "clips"
        self.final_dir = self.data_dir / "final"
        self.logs_dir = self.output_dir / "logs"
        
        # Create all required directories
        for dir_path in [self.downloads_dir, self.transcripts_dir, 
                         self.clips_dir, self.final_dir, self.logs_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {dir_path}")
    
    def setup_environment(self):
        """Set up test environment variables."""
        os.environ["BASE_DIR"] = str(self.data_dir)
        
        if self.debug:
            os.environ["FFREPORT"] = f"file={self.logs_dir}/ffmpeg_%t_%p.log:level=debug"
        
        # Log environment information
        logger.debug(f"Python executable: {sys.executable}")
        logger.debug(f"Working directory: {os.getcwd()}")
        logger.debug(f"Environment variables: {dict(os.environ)}")
        
        # Log FFmpeg version
        self.log_command_info("ffmpeg")
        self.log_command_info("ffprobe")
    
    def log_command_info(self, command: str):
        """Log version information for a command."""
        try:
            result = subprocess.run(
                [command, "-version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                version = result.stdout.split('\n')[0].strip()
                logger.info(f"{command} version: {version}")
            else:
                logger.warning(f"Could not get {command} version: {result.stderr}")
        except Exception as e:
            logger.warning(f"Error getting {command} version: {str(e)}")
    
    def run_test(self) -> bool:
        """Run the complete test pipeline."""
        self.log_phase("STARTING TEST")
        
        try:
            # 1. Prepare test video
            self.log_phase("PREPARING TEST VIDEO")
            if not self.prepare_test_video():
                return False
            
            # 2. Generate test transcript
            self.log_phase("GENERATING TEST TRANSCRIPT")
            if not self.generate_test_transcript():
                return False
            
            # 3. Generate test clips
            self.log_phase("GENERATING TEST CLIPS")
            if not self.generate_test_clips():
                return False
            
            # 4. Test rendering
            self.log_phase("TESTING RENDERING")
            if not self.test_rendering():
                return False
            
            # 5. Validate output
            self.log_phase("VALIDATING OUTPUT")
            if not self.validate_output():
                return False
            
            self.log_phase("TEST COMPLETED SUCCESSFULLY")
            return True
            
        except Exception as e:
            logger.error(f"Test failed with error: {str(e)}", exc_info=True)
            return False
    
    def prepare_test_video(self) -> bool:
        """Prepare the test video file."""
        if USE_SHORT_VIDEO and os.path.exists(SHORT_VIDEO_PATH):
            self.video_path = Path(SHORT_VIDEO_PATH).resolve()
            logger.info(f"Using local test video: {self.video_path}")
            return True
        
        # Download video if needed
        self.video_path = self.downloads_dir / "test_video.mp4"
        if self.video_path.exists():
            logger.info(f"Using existing test video: {self.video_path}")
            return True
            
        logger.info(f"Downloading test video to {self.video_path}...")
        success, _ = run_command(
            [
                'yt-dlp',
                '-f', 'best[height<=480]',
                '-o', str(self.video_path),
                '--no-playlist',
                '--merge-output-format', 'mp4',
                TEST_VIDEO_URL
            ],
            timeout=600,  # 10 minutes for download
            log_output=True
        )
        
        if success and self.video_path.exists():
            logger.info(f"Successfully downloaded video ({self.video_path.stat().st_size / (1024*1024):.1f}MB)")
            return True
        
        logger.error("Failed to prepare test video")
        return False
    
    def generate_test_transcript(self) -> bool:
        """Generate a test transcript file."""
        transcript_path = self.transcripts_dir / "test_video.json"
        
        # Simple test transcript
        transcript = {
            "segments": [
                {"start": 0.0, "end": 5.0, "text": "This is a test video transcript."},
                {"start": 5.0, "end": 10.0, "text": "It contains sample text for testing captions."}
            ]
        }
        
        try:
            with open(transcript_path, 'w') as f:
                json.dump(transcript, f, indent=2)
            logger.info(f"Generated test transcript at {transcript_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to generate transcript: {str(e)}")
            return False
    
    def generate_test_clips(self) -> bool:
        """Generate test clip configuration."""
        clips_path = self.clips_dir / "test_video_clips.json"
        
        clips = {
            "recommended_clips": [
                {"start": 0.0, "end": 5.0, "score": 0.95, "reason": "Test clip 1"},
                {"start": 5.0, "end": 10.0, "score": 0.92, "reason": "Test clip 2"}
            ]
        }
        
        try:
            with open(clips_path, 'w') as f:
                json.dump(clips, f, indent=2)
            logger.info(f"Generated test clips at {clips_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to generate clip configuration: {str(e)}")
            return False
    
    def test_rendering(self) -> bool:
        """Test rendering with different configurations."""
        test_cases = [
            ("original", False, False),
            ("vertical", True, False),
            ("square", True, True)
        ]
        
        all_success = True
        
        for format, add_captions, normalize_audio in test_cases:
            logger.info(f"Testing format={format}, captions={add_captions}, normalize_audio={normalize_audio}")
            
            output_file = self.final_dir / f"test_clip_{format}.mp4"
            
            # Build the command with full path to the renderer
            renderer_dir = Path(__file__).parent.parent / "services" / "clip-renderer"
            cmd = [
                sys.executable, "-m", "app.main", "render",
                "--video", str(self.video_path.name),
                "--format", format,
                "--output-dir", str(self.final_dir)
            ]
            
            if add_captions:
                cmd.append("--add-captions")
            if normalize_audio:
                cmd.append("--normalize-audio")
            
            # Set up environment with PYTHONPATH
            env = os.environ.copy()
            env["PYTHONPATH"] = str(renderer_dir) + (f":{env['PYTHONPATH']}" if 'PYTHONPATH' in env else "")
            
            # Run the command in the renderer directory
            start_time = time.time()
            success, output = run_command(
                cmd,
                cwd=str(renderer_dir),  # Run from the renderer directory
                env=env,
                timeout=300,  # 5 minutes per render
                log_output=True
            )
            
            elapsed = time.time() - start_time
            if success:
                logger.info(f"Successfully rendered {format} in {elapsed:.1f}s")
                if output_file.exists():
                    size_mb = output_file.stat().st_size / (1024 * 1024)
                    logger.info(f"Output file: {output_file} ({size_mb:.1f}MB)")
                else:
                    logger.warning(f"Expected output file not found: {output_file}")
                    all_success = False
            else:
                logger.error(f"Failed to render {format}: {output}")
                all_success = False
        
        return all_success
    
    def validate_output(self) -> bool:
        """Validate the output files."""
        valid = True
        
        # Check for expected output files
        expected_formats = ["original", "vertical", "square"]
        for fmt in expected_formats:
            output_file = self.final_dir / f"test_clip_{fmt}.mp4"
            if output_file.exists():
                size_mb = output_file.stat().st_size / (1024 * 1024)
                logger.info(f"✓ Found {output_file.name} ({size_mb:.1f}MB)")
                
                # Basic file validation
                if size_mb < 0.1:  # Less than 100KB is suspicious
                    logger.warning(f"File {output_file.name} is unusually small")
                    valid = False
            else:
                logger.error(f"✗ Missing output file: {output_file.name}")
                valid = False
        
        return valid

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test the Clip Renderer pipeline")
    parser.add_argument("--output-dir", "-o", default="test_output",
                       help="Output directory for test files")
    parser.add_argument("--debug", "-d", action="store_true",
                       help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Run the test pipeline
    pipeline = TestPipeline(output_dir=args.output_dir, debug=args.debug)
    success = pipeline.run_test()
    
    if success:
        logger.info("✅ All tests passed!")
        return 0
    else:
        logger.error("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
