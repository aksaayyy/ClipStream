#!/usr/bin/env python3
"""
Fixed test script for Clip Renderer with proper environment setup.
"""

import os
import sys
import json
import time
import shutil
import logging
import subprocess
from pathlib import Path
from typing import List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)-8s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_renderer.log')
    ]
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_TIMEOUT = 300  # 5 minutes
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
SHORT_VIDEO_PATH = "test_assets/short_test.mp4"

class TestRenderer:
    def __init__(self, output_dir: str = "test_output", debug: bool = False):
        """Initialize the test renderer."""
        self.output_dir = Path(output_dir).resolve()
        self.debug = debug
        self.setup_directories()
        self.setup_environment()
        logger.info(f"Test renderer initialized in {self.output_dir}")
    
    def setup_directories(self):
        """Set up test directories."""
        self.data_dir = self.output_dir / "data"
        self.downloads_dir = self.data_dir / "downloads"
        self.transcripts_dir = self.data_dir / "transcripts"
        self.clips_dir = self.data_dir / "clips"
        self.final_dir = self.data_dir / "final"
        self.logs_dir = self.output_dir / "logs"
        
        for d in [self.downloads_dir, self.transcripts_dir, 
                 self.clips_dir, self.final_dir, self.logs_dir]:
            d.mkdir(parents=True, exist_ok=True)
    
    def setup_environment(self):
        """Set up environment variables."""
        self.env = os.environ.copy()
        self.env["BASE_DIR"] = str(self.data_dir)
        
        # Enable FFmpeg debug logging
        ffmpeg_log = self.logs_dir / "ffmpeg_%t_%p.log"
        self.env["FFREPORT"] = f"file={ffmpeg_log}:level=debug"
        
        # Set Python path to include the renderer
        renderer_dir = Path(__file__).parent.parent / "services" / "clip-renderer"
        self.env["PYTHONPATH"] = str(renderer_dir)
        
        logger.debug(f"Python path: {self.env['PYTHONPATH']}")
    
    def run_test(self) -> bool:
        """Run the complete test."""
        logger.info("=" * 80)
        logger.info("STARTING RENDERER TEST")
        logger.info("=" * 80)
        
        try:
            if not self.prepare_test_video():
                return False
                
            if not self.generate_test_data():
                return False
                
            return self.test_rendering()
            
        except Exception as e:
            logger.error(f"Test failed: {str(e)}", exc_info=True)
            return False
    
    def prepare_test_video(self) -> bool:
        """Prepare the test video file."""
        self.video_path = Path(SHORT_VIDEO_PATH) if os.path.exists(SHORT_VIDEO_PATH) else self.downloads_dir / "test_video.mp4"
        
        if self.video_path.exists():
            logger.info(f"Using test video: {self.video_path}")
            return True
            
        logger.info(f"Downloading test video to {self.video_path}...")
        return self.run_command([
            'yt-dlp',
            '-f', 'best[height<=480]',
            '-o', str(self.video_path),
            '--no-playlist',
            '--merge-output-format', 'mp4',
            TEST_VIDEO_URL
        ], timeout=600)[0]
    
    def generate_test_data(self) -> bool:
        """Generate test transcript and clips."""
        # Generate test transcript
        transcript_path = self.transcripts_dir / "test_video.json"
        with open(transcript_path, 'w') as f:
            json.dump({
                "segments": [
                    {"start": 0.0, "end": 5.0, "text": "Test caption 1"},
                    {"start": 5.0, "end": 10.0, "text": "Test caption 2"}
                ]
            }, f, indent=2)
        
        # Generate test clips
        clips_path = self.clips_dir / "test_video_clips.json"
        with open(clips_path, 'w') as f:
            json.dump({
                "recommended_clips": [
                    {"start": 0.0, "end": 5.0, "score": 0.95, "reason": "Test clip 1"},
                    {"start": 5.0, "end": 10.0, "score": 0.92, "reason": "Test clip 2"}
                ]
            }, f, indent=2)
            
        logger.info("Generated test data")
        return True
    
    def test_rendering(self) -> bool:
        """Test rendering with different configurations."""
        test_cases = [
            ("original", False, False),
            ("vertical", True, False),
            ("square", True, True)
        ]
        
        renderer_dir = Path(__file__).parent.parent / "services" / "clip-renderer"
        all_success = True
        
        for fmt, captions, normalize in test_cases:
            output_file = self.final_dir / f"test_clip_{fmt}.mp4"
            
            # Build command
            cmd = [
                sys.executable, "-m", "app.main", "render",
                "--video", str(self.video_path.name),
                "--format", fmt,
                "--output-dir", str(self.final_dir)
            ]
            if captions:
                cmd.append("--add-captions")
            if normalize:
                cmd.append("--normalize-audio")
            
            logger.info(f"\nTesting format={fmt}, captions={captions}, normalize={normalize}")
            
            # Run the command
            success, output = self.run_command(
                cmd,
                cwd=str(renderer_dir),  # Critical: Run from renderer directory
                timeout=300
            )
            
            if success and output_file.exists():
                size_mb = output_file.stat().st_size / (1024 * 1024)
                logger.info(f"✓ Success: {output_file.name} ({size_mb:.1f}MB)")
            else:
                logger.error(f"✗ Failed to generate {fmt}")
                all_success = False
        
        return all_success
    
    def run_command(self, cmd: List[str], **kwargs) -> Tuple[bool, str]:
        """Run a command with proper logging and error handling."""
        # Set defaults
        stdout = subprocess.PIPE
        stderr = subprocess.STDOUT
        text = True
        env = self.env
        timeout = kwargs.get('timeout', DEFAULT_TIMEOUT)
        cwd = kwargs.get('cwd')
        
        # Log the command
        logger.debug(f"Running: {' '.join(cmd)}")
        if cwd:
            logger.debug(f"Working directory: {cwd}")
        
        try:
            # Run the command
            process = subprocess.Popen(
                cmd,
                stdout=stdout,
                stderr=stderr,
                text=text,
                env=env,
                cwd=cwd
            )
            
            try:
                stdout, _ = process.communicate(timeout=timeout)
                
                if process.returncode == 0:
                    return True, stdout or ""
                
                error_msg = f"Command failed with code {process.returncode}"
                if stdout:
                    error_msg += f"\n{stdout}"
                logger.error(error_msg)
                return False, error_msg
                
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                
                error_msg = f"Command timed out after {timeout}s"
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Error running command: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test the Clip Renderer")
    parser.add_argument("--output-dir", "-o", default="test_output",
                      help="Output directory for test files")
    parser.add_argument("--debug", "-d", action="store_true",
                      help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Set log level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run the test
    test = TestRenderer(output_dir=args.output_dir, debug=args.debug)
    success = test.run_test()
    
    if success:
        logger.info("✅ All tests passed!")
        return 0
    else:
        logger.error("❌ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
