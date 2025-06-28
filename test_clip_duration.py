#!/usr/bin/env python3
"""
Test script to verify 15-second clip duration enforcement.
"""
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Add the project root to the Python path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# Import from the clip-renderer service using the correct path
sys.path.append(str(project_root / "services" / "clip-renderer"))
from app.renderer import VideoRenderer
from app.segment_cutter import get_video_duration

def create_test_clips(video_path, output_dir):
    """Create test clips with different duration scenarios."""
    # Get video duration
    duration = get_video_duration(video_path)
    print(f"Source video duration: {duration:.2f} seconds")
    
    # Create test clips configuration
    test_clips = {
        "recommended_clips": [
            # Clip longer than 15 seconds (should be centered)
            {"start": 0, "end": min(30, duration), "text": "Long clip"},
            # Clip shorter than 15 seconds (should be padded)
            {"start": 0, "end": min(5, duration), "text": "Short clip"},
            # Clip exactly 15 seconds (should remain unchanged if possible)
            {"start": 0, "end": min(15, duration), "text": "Perfect clip"}
        ]
    }
    
    # Save clips config
    clips_path = os.path.join(output_dir, "test_clips.json")
    with open(clips_path, 'w') as f:
        json.dump(test_clips, f, indent=2)
    
    return clips_path

def main():
    # Set up directories
    test_dir = Path("test_output")
    test_dir.mkdir(exist_ok=True)
    
    # Use the first command line argument as video path, or use a default test video
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
    else:
        video_path = "test_video.mp4"
        print("No video path provided. Using default test video.")
    
    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        sys.exit(1)
    
    # Create test clips configuration
    print("Creating test clips configuration...")
    clips_path = create_test_clips(video_path, test_dir)
    
    # Initialize the renderer
    print("Initializing video renderer...")
    renderer = VideoRenderer()
    
    # Create output directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = test_dir / f"clips_{timestamp}"
    output_dir.mkdir(exist_ok=True)
    
    # Set up test directories
    os.makedirs("data/downloads", exist_ok=True)
    os.makedirs("data/transcripts", exist_ok=True)
    
    # Create a symlink in the expected downloads directory
    symlink_path = os.path.join("data/downloads", os.path.basename(video_path))
    if os.path.exists(symlink_path):
        os.remove(symlink_path)
    os.symlink(os.path.abspath(video_path), symlink_path)
    
    # Create a mock transcript file
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    
    # Create transcript file
    transcript_path = os.path.join("data/transcripts", f"{video_name}.json")
    mock_transcript = {
        "text": "This is a test transcript for clip duration testing.",
        "segments": [
            {"start": 0.0, "end": 30.0, "text": "Long clip"},
            {"start": 0.0, "end": 5.0, "text": "Short clip"},
            {"start": 0.0, "end": 15.0, "text": "Perfect clip"}
        ]
    }
    with open(transcript_path, 'w') as f:
        json.dump(mock_transcript, f)
    
    # Create clips file
    os.makedirs("data/clips", exist_ok=True)
    clips_path = os.path.join("data/clips", f"{video_name}_clips.json")
    mock_clips = {
        "recommended_clips": [
            {"start": 0.0, "end": 30.0, "text": "Long clip"},
            {"start": 0.0, "end": 5.0, "text": "Short clip"},
            {"start": 0.0, "end": 15.0, "text": "Perfect clip"}
        ]
    }
    with open(clips_path, 'w') as f:
        json.dump(mock_clips, f)
    
    # Render the clips
    print(f"Rendering clips to {output_dir}...")
    success, clips, error = renderer.render_clips(
        video_name=os.path.basename(video_path),
        output_dir=output_dir,
        format="vertical",
        add_captions=True,
        normalize_audio=True
    )
    
    if not success:
        print(f"Error rendering clips: {error}")
        sys.exit(1)
    
    # Verify the clips
    print("\nVerifying clip durations...")
    for i, clip_path in enumerate(clips, 1):
        duration = get_video_duration(clip_path)
        print(f"Clip {i}: {os.path.basename(clip_path)} - {duration:.2f} seconds")
        assert abs(duration - 15.0) < 0.5, f"Clip {i} is {duration:.2f}s, expected 15.0s"
    
    print("\nAll clips are approximately 15 seconds long!")
    print(f"Output directory: {output_dir.absolute()}")

if __name__ == "__main__":
    main()
