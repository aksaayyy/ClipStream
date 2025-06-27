#!/usr/bin/env python3
"""
End-to-end test script for the clip-renderer service.

This script tests the entire clip rendering pipeline:
1. Downloads a test video
2. Creates a sample transcript
3. Creates a sample clips configuration
4. Renders clips using the VideoRenderer
5. Validates the output
"""

import os
import json
import argparse
import tempfile
from pathlib import Path
import subprocess
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
TEST_VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
TEST_VIDEO_DURATION = 213  # seconds
TEST_CLIPS = [
    {"start": 10, "end": 20, "score": 0.95, "reason": "Test clip 1"},
    {"start": 60, "end": 70, "score": 0.92, "reason": "Test clip 2"},
]

def download_test_video(output_dir: Path) -> Path:
    """Download a test video using yt-dlp."""
    video_path = output_dir / "test_video.mp4"
    if not video_path.exists():
        logger.info(f"Downloading test video to {video_path}...")
        cmd = [
            "yt-dlp",
            "-f", "best[height<=720]",  # 720p or lower
            "-o", str(video_path),
            "--no-playlist",
            TEST_VIDEO_URL
        ]
        subprocess.run(cmd, check=True)
    else:
        logger.info(f"Using existing test video at {video_path}")
    return video_path

def create_test_transcript(output_dir: Path) -> Path:
    """Create a test transcript file."""
    transcript_path = output_dir / "test_transcript.json"
    transcript = {
        "segments": [
            {
                "start": 10,
                "end": 20,
                "text": "Never gonna give you up, never gonna let you down"
            },
            {
                "start": 60,
                "end": 70,
                "text": "Never gonna run around and desert you"
            }
        ]
    }
    
    with open(transcript_path, 'w') as f:
        json.dump(transcript, f, indent=2)
    
    return transcript_path

def create_test_clips(output_dir: Path) -> Path:
    """Create a test clips configuration file."""
    clips_path = output_dir / "test_clips.json"
    clips = {
        "recommended_clips": TEST_CLIPS
    }
    
    with open(clips_path, 'w') as f:
        json.dump(clips, f, indent=2)
    
    return clips_path

def main():
    parser = argparse.ArgumentParser(description="Test clip-renderer end-to-end")
    parser.add_argument("--output-dir", type=str, default="test_output",
                       help="Output directory for test files")
    parser.add_argument("--keep-files", action="store_true",
                       help="Keep intermediate files after test")
    args = parser.parse_args()
    
    # Set up directories
    output_dir = Path(args.output_dir).absolute()
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Set up test data paths
    data_dir = output_dir / "test_data"
    data_dir.mkdir(exist_ok=True)
    
    # Create test files
    try:
        logger.info("Setting up test files...")
        video_path = download_test_video(data_dir)
        transcript_path = create_test_transcript(data_dir)
        clips_path = create_test_clips(data_dir)
        
        # Set up the renderer
        from app.renderer import VideoRenderer
        from app.segment_cutter import cut_segment
        
        renderer = VideoRenderer()
        
        # Test 1: Basic clip rendering
        logger.info("Testing basic clip rendering...")
        success, clips, error = renderer.render_clips(
            video_name=video_path.name,
            output_dir=output_dir / "basic",
            base_dir=data_dir
        )
        
        assert success, f"Basic clip rendering failed: {error}"
        assert len(clips) == len(TEST_CLIPS), f"Expected {len(TEST_CLIPS)} clips, got {len(clips)}"
        
        # Test 2: Vertical format
        logger.info("Testing vertical format...")
        success, clips, error = renderer.render_clips(
            video_name=video_path.name,
            format="vertical",
            output_dir=output_dir / "vertical",
            base_dir=data_dir
        )
        
        assert success, f"Vertical format rendering failed: {error}"
        
        # Test 3: With captions
        logger.info("Testing with captions...")
        success, clips, error = renderer.render_clips(
            video_name=video_path.name,
            add_captions=True,
            output_dir=output_dir / "with_captions",
            base_dir=data_dir
        )
        
        assert success, f"Rendering with captions failed: {error}"
        
        logger.info("All tests passed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        return 1
    finally:
        # Clean up
        if not args.keep_files and data_dir.exists():
            import shutil
            shutil.rmtree(data_dir)
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
