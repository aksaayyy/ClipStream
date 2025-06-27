#!/usr/bin/env python3
"""
Test script for the clip-renderer service.
This script tests the clip-renderer with a minimal test case.
"""
import os
import sys
import json
import shutil
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("test_clip_renderer")

def setup_test_environment():
    """Set up the test environment with required files."""
    test_dir = Path(__file__).parent
    input_dir = test_dir / "input"
    output_dir = test_dir / "output"
    config_dir = test_dir / "config"
    
    # Create directories if they don't exist
    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    config_dir.mkdir(exist_ok=True)
    
    # Copy test video if it doesn't exist
    test_video = input_dir / "test_video.mp4"
    if not test_video.exists():
        src_video = Path("services/clip-renderer/test_assets/short_test.mp4")
        if src_video.exists():
            shutil.copy2(src_video, test_video)
            logger.info(f"Copied test video to {test_video}")
        else:
            logger.error(f"Source test video not found at {src_video}")
            return False
    
    # Create a simple transcript file
    transcript_file = config_dir / "test_video.json"
    if not transcript_file.exists():
        transcript = {
            "text": "This is a test video transcript. It contains sample text for testing captions.",
            "segments": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "text": "This is a test video transcript.",
                    "words": [
                        {"start": 0.0, "end": 0.5, "word": "This"},
                        {"start": 0.5, "end": 1.0, "word": "is"},
                        {"start": 1.0, "end": 1.5, "word": "a"},
                        {"start": 1.5, "end": 2.0, "word": "test"},
                        {"start": 2.0, "end": 2.5, "word": "video"},
                        {"start": 2.5, "end": 3.0, "word": "transcript"},
                        {"start": 3.0, "end": 3.5, "word": "."}
                    ]
                },
                {
                    "start": 3.5,
                    "end": 8.0,
                    "text": "It contains sample text for testing captions.",
                    "words": [
                        {"start": 3.5, "end": 4.0, "word": "It"},
                        {"start": 4.0, "end": 4.5, "word": "contains"},
                        {"start": 4.5, "end": 5.0, "word": "sample"},
                        {"start": 5.0, "end": 5.5, "word": "text"},
                        {"start": 5.5, "end": 6.0, "word": "for"},
                        {"start": 6.0, "end": 6.5, "word": "testing"},
                        {"start": 6.5, "end": 7.0, "word": "captions"},
                        {"start": 7.0, "end": 7.5, "word": "."}
                    ]
                }
            ]
        }
        with open(transcript_file, 'w') as f:
            json.dump(transcript, f, indent=2)
        logger.info(f"Created test transcript at {transcript_file}")
    
    # Create a simple clips configuration
    clips_file = config_dir / "test_video_clips.json"
    if not clips_file.exists():
        clips_config = {
            "recommended_clips": [
                {
                    "start": 0.0,
                    "end": 5.0,
                    "score": 0.9,
                    "reason": "Test clip 1"
                },
                {
                    "start": 5.0,
                    "end": 10.0,
                    "score": 0.8,
                    "reason": "Test clip 2"
                }
            ]
        }
        with open(clips_file, 'w') as f:
            json.dump(clips_config, f, indent=2)
        logger.info(f"Created test clips config at {clips_file}")
    
    return True

def run_test():
    """Run the clip-renderer test."""
    logger.info("Starting clip-renderer test...")
    
    # Set up test environment
    if not setup_test_environment():
        logger.error("Failed to set up test environment")
        return False
    
    test_dir = Path(__file__).parent
    input_dir = test_dir / "input"
    output_dir = test_dir / "output"
    config_dir = test_dir / "config"
    
    # Create symbolic links to make the test directory structure match the expected layout
    data_dir = test_dir / "data"
    data_dir.mkdir(exist_ok=True)
    
    # Create symlinks for the expected directory structure
    for src, dest in [
        (input_dir, data_dir / "downloads"),
        (config_dir / "test_video.json", data_dir / "transcripts" / "test_video.json"),
        (config_dir / "test_video_clips.json", data_dir / "clips" / "test_video_clips.json"),
        (output_dir, data_dir / "final")
    ]:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            try:
                dest.symlink_to(src.resolve(), target_is_directory=src.is_dir())
                logger.info(f"Created symlink: {dest} -> {src}")
            except FileExistsError:
                pass
    
    # Run the clip-renderer
    import subprocess
    
    cmd = [
        sys.executable, "-m", "app.main", "render",
        "--video", "test_video.mp4",
        "--format", "vertical",
        "--add-captions",
        "--normalize-audio",
        "--output-dir", str(data_dir / "final")
    ]
    
    logger.info(f"Running command: {' '.join(cmd)}")
    
    try:
        # Set the BASE_DIR environment variable
        env = os.environ.copy()
        env["BASE_DIR"] = str(data_dir)
        
        # Run the command
        result = subprocess.run(
            cmd,
            cwd="services/clip-renderer",
            env=env,
            capture_output=True,
            text=True
        )
        
        # Log the output
        logger.info("=" * 80)
        logger.info("Command output:")
        logger.info(result.stdout)
        
        if result.stderr:
            logger.error("Command errors:")
            logger.error(result.stderr)
        
        # Check for output files
        output_files = list((data_dir / "final").glob("*.mp4"))
        if output_files:
            logger.info("Generated output files:")
            for f in output_files:
                logger.info(f"- {f}")
            return True
        else:
            logger.error("No output files were generated")
            return False
            
    except Exception as e:
        logger.error(f"Error running command: {e}")
        return False

if __name__ == "__main__":
    if run_test():
        logger.info("Test completed successfully")
        sys.exit(0)
    else:
        logger.error("Test failed")
        sys.exit(1)
