import os
import json
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.renderer import VideoRenderer
from app.segment_cutter import cut_segment
from app.caption_overlay import add_captions

# Test data
SAMPLE_VIDEO = "test_video.mp4"
SAMPLE_TRANSCRIPT = "test_video.json"
SAMPLE_CLIPS = "test_video_clips.json"
TEST_DATA_DIR = Path(__file__).parent / "test_data"

# Create test data directory if it doesn't exist
TEST_DATA_DIR.mkdir(exist_ok=True)

# Sample transcript data
SAMPLE_TRANSCRIPT_DATA = {
    "segments": [
        {"start": 0, "end": 5, "text": "This is a test caption"},
        {"start": 5, "end": 10, "text": "For the test video"},
    ]
}

# Sample clips data
SAMPLE_CLIPS_DATA = {
    "recommended_clips": [
        {"start": 0, "end": 10, "score": 0.95, "reason": "Test clip"}
    ]
}

# Create sample files for testing
with open(TEST_DATA_DIR / SAMPLE_TRANSCRIPT, 'w') as f:
    json.dump(SAMPLE_TRANSCRIPT_DATA, f)

with open(TEST_DATA_DIR / SAMPLE_CLIPS, 'w') as f:
    json.dump(SAMPLE_CLIPS_DATA, f)

# Create a small test video (1 second of black video with silent audio)
os.system(f'ffmpeg -y -f lavfi -i testsrc=duration=1:size=1280x720:rate=30 -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 -c:v libx264 -t 1 -pix_fmt yuv420p {TEST_DATA_DIR / SAMPLE_VIDEO}')

class TestVideoRenderer:
    def setup_method(self):
        """Set up test environment before each test."""
        self.renderer = VideoRenderer()
        self.test_video = str(TEST_DATA_DIR / SAMPLE_VIDEO)
        self.test_transcript = str(TEST_DATA_DIR / SAMPLE_TRANSCRIPT)
        self.test_clips = str(TEST_DATA_DIR / SAMPLE_CLIPS)
        self.output_dir = tempfile.mkdtemp()
        
        # Create a longer test video (30 seconds) for duration testing
        self.long_video = str(TEST_DATA_DIR / "long_test_video.mp4")
        if not os.path.exists(self.long_video):
            os.system(f'ffmpeg -y -f lavfi -i testsrc=duration=30:size=1280x720:rate=30 -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 -c:v libx264 -t 30 -pix_fmt yuv420p {self.long_video}')

    def test_render_clips_duration_enforcement(self):
        """Test that clips are exactly 15 seconds long."""
        # Create a test clips file with different duration scenarios
        test_clips = {
            "recommended_clips": [
                # Clip longer than 15 seconds (should be centered)
                {"start": 0, "end": 30, "text": "Long clip"},
                # Clip shorter than 15 seconds (should be padded)
                {"start": 0, "end": 5, "text": "Short clip"},
                # Clip exactly 15 seconds (should remain unchanged)
                {"start": 0, "end": 15, "text": "Perfect clip"}
            ]
        }
        
        # Save test clips to a temporary file
        test_clips_path = os.path.join(self.output_dir, "test_clips.json")
        with open(test_clips_path, 'w') as f:
            json.dump(test_clips, f)
        
        # Set up the renderer with our test files
        renderer = VideoRenderer()
        
        # Mock the _get_file_paths method to return our test files
        with patch('app.renderer.VideoRenderer._get_file_paths') as mock_paths:
            mock_paths.return_value = (
                Path(self.long_video),  # Use our 30s test video
                Path(self.test_transcript),
                Path(test_clips_path)
            )
            
            # Call the method under test
            success, clips, error = renderer.render_clips(
                video_name="long_test_video.mp4",
                output_dir=self.output_dir,
                add_captions=False  # Disable captions for this test
            )
        
        # Verify the results
        assert success is True, f"render_clips failed with error: {error}"
        assert len(clips) == 3, f"Expected 3 clips, got {len(clips)}"
        
        # Verify each clip is exactly 15 seconds long
        from app.segment_cutter import get_video_duration
        
        for i, clip_path in enumerate(clips):
            duration = get_video_duration(clip_path)
            assert abs(duration - 15.0) < 0.1, f"Clip {i+1} is {duration:.2f}s, expected 15.0s"
            
            # Clean up
            if os.path.exists(clip_path):
                os.remove(clip_path)
    
    def test_render_clips_basic(self, mock_add_captions, mock_paths):
        """Test basic clip rendering functionality."""
        # Set up the mocks
        mock_paths.return_value = (
            Path(self.test_video),
            Path(self.test_transcript),
            Path(self.test_clips)
        )
        
        # Mock the add_captions function to return success
        output_path = str(Path(self.output_dir) / "test_output.mp4")
        mock_add_captions.return_value = (True, output_path)
        
        # Call the method under test
        success, clips, error = self.renderer.render_clips(
            video_name=SAMPLE_VIDEO,
            output_dir=self.output_dir,
            add_captions=True  # Explicitly enable captions for the test
        )
        
        # Debug output
        print(f"Success: {success}")
        print(f"Clips: {clips}")
        print(f"Error: {error}")
        
        # Verify the results
        assert success is True, f"render_clips failed with error: {error}"
        assert len(clips) == 1, f"Expected 1 clip, got {len(clips)}"
        
        # Verify the output file exists and has content
        output_path = Path(clips[0])
        assert output_path.exists(), f"Output file {output_path} does not exist"
        assert output_path.stat().st_size > 0, f"Output file {output_path} is empty"
        assert output_path.suffix == '.mp4', f"Expected .mp4 file, got {output_path}"
        
        # Verify add_captions was called with the expected arguments
        mock_add_captions.assert_called_once()
        
        # Get the call arguments (both positional and keyword)
        args, kwargs = mock_add_captions.call_args
        
        # The first argument should be the video path (output_path without _captioned)
        expected_video_path = str(Path(self.output_dir) / f"{SAMPLE_VIDEO.split('.')[0]}_clip_1.mp4")
        
        # Check if arguments were passed as positional or keyword args
        if args:
            # Positional arguments
            assert len(args) >= 2, f"Expected at least 2 positional arguments, got {len(args)}"
            assert str(args[0]) == expected_video_path, f"Unexpected video path: {args[0]}"
            assert str(args[1]) == str(Path(self.test_transcript)), f"Unexpected transcript path: {args[1]}"
        else:
            # Keyword arguments
            assert 'video_path' in kwargs, "Missing 'video_path' in keyword arguments"
            assert 'transcript_path' in kwargs, "Missing 'transcript_path' in keyword arguments"
            assert str(kwargs['video_path']) == expected_video_path, f"Unexpected video path: {kwargs['video_path']}"
            assert str(kwargs['transcript_path']) == str(Path(self.test_transcript)), f"Unexpected transcript path: {kwargs['transcript_path']}"
    
    def test_video_formats(self):
        """Test rendering with different video formats."""
        formats = ["vertical", "square", "original"]
        
        for fmt in formats:
            with patch('app.renderer.VideoRenderer._get_file_paths') as mock_paths:
                mock_paths.return_value = (
                    Path(self.test_video),
                    Path(self.test_transcript),
                    Path(self.test_clips)
                )
                
                success, clips, error = self.renderer.render_clips(
                    video_name=SAMPLE_VIDEO,
                    format=fmt,
                    output_dir=self.output_dir
                )
                
                assert success is True
                assert len(clips) == 1
                assert os.path.exists(clips[0])
    
    @patch('app.caption_overlay.add_captions')
    def test_caption_addition(self, mock_add_captions):
        """Test that captions are added when requested."""
        # Mock the return value for add_captions
        output_path = str(Path(self.output_dir) / "test_output.mp4")
        mock_add_captions.return_value = (True, output_path)

        # Mock the file paths
        with patch('app.renderer.VideoRenderer._get_file_paths') as mock_paths:
            mock_paths.return_value = (
                Path(self.test_video),
                Path(self.test_transcript),
                Path(self.test_clips)
            )

            # Call the method under test
            success, clips, error = self.renderer.render_clips(
                video_name=SAMPLE_VIDEO,
                add_captions=True,
                output_dir=self.output_dir
            )

            # Verify the results
            assert success is True, f"render_clips failed with error: {error}"
            assert len(clips) == 1, f"Expected 1 clip, got {len(clips)}"
            
            # Verify add_captions was called with the expected arguments
            mock_add_captions.assert_called_once()
            args, kwargs = mock_add_captions.call_args
            
            # Check if arguments were passed as positional or keyword args
            if args:
                # Positional arguments
                assert len(args) >= 2, f"Expected at least 2 positional arguments, got {len(args)}"
                assert str(args[0]).endswith('.mp4'), f"Expected video path, got {args[0]}"
                assert str(args[1]) == str(Path(self.test_transcript)), f"Unexpected transcript path: {args[1]}"
            else:
                # Keyword arguments
                assert 'video_path' in kwargs, "Missing 'video_path' in keyword arguments"
                assert 'transcript_path' in kwargs, "Missing 'transcript_path' in keyword arguments"
                assert str(kwargs['video_path']).endswith('.mp4'), f"Expected video path, got {kwargs['video_path']}"
                assert str(kwargs['transcript_path']) == str(Path(self.test_transcript)), f"Unexpected transcript path: {kwargs['transcript_path']}"
    
    def test_error_handling(self):
        """Test error handling for missing files."""
        with pytest.raises(FileNotFoundError):
            self.renderer.render_clips(
                video_name="nonexistent_video.mp4",
                output_dir=self.output_dir
            )

class TestSegmentCutter:
    def setup_method(self):
        """Set up test environment before each test."""
        self.test_video = str(TEST_DATA_DIR / SAMPLE_VIDEO)
        
    def test_cut_segment_basic(self):
        """Test basic segment cutting."""
        output_path = os.path.join(tempfile.mkdtemp(), "output.mp4")
        success, message = cut_segment(
            input_path=self.test_video,
            output_path=output_path,
            start_time=0,
            end_time=0.5  # Cut a 0.5s segment
        )
        
        assert success is True
        assert os.path.exists(output_path)
    
    def test_video_formats(self):
        """Test cutting with different video formats."""
        formats = ["vertical", "square", "original"]
        
        for fmt in formats:
            output_path = os.path.join(tempfile.mkdtemp(), f"output_{fmt}.mp4")
            success, message = cut_segment(
                input_path=self.test_video,
                output_path=output_path,
                start_time=0,
                end_time=0.5,
                video_format=fmt
            )
            
            assert success is True
            assert os.path.exists(output_path)

class TestCaptionOverlay:
    def setup_method(self):
        """Set up test environment before each test."""
        self.test_video = str(TEST_DATA_DIR / SAMPLE_VIDEO)
        self.test_transcript = str(TEST_DATA_DIR / SAMPLE_TRANSCRIPT)
        self.output_dir = tempfile.mkdtemp()
        self.output_path = os.path.join(self.output_dir, "output_with_captions.mp4")
    
    def test_add_captions_basic(self):
        """Test basic caption overlay functionality."""
        success, output_file = add_captions(
            video_path=self.test_video,
            transcript_path=self.test_transcript,
            output_path=self.output_path
        )
        
        assert success is True
        assert os.path.exists(output_file)
        assert os.path.getsize(output_file) > 0
    
    def test_add_captions_different_styles(self):
        """Test caption overlay with different style presets."""
        style_presets = ["youtube", "tiktok", "instagram"]
        
        for preset in style_presets:
            output_path = os.path.join(self.output_dir, f"output_{preset}.mp4")
            success, output_file = add_captions(
                video_path=self.test_video,
                transcript_path=self.test_transcript,
                output_path=output_path,
                style_preset=preset
            )
            
            assert success is True, f"Failed with style preset: {preset}"
            assert os.path.exists(output_file), f"Output file not created for preset: {preset}"
            assert os.path.getsize(output_file) > 0, f"Empty output file for preset: {preset}"
    
    def test_add_captions_with_custom_style(self):
        """Test caption overlay with custom style overrides."""
        custom_style = {
            "fontname": "Arial",
            "fontsize": 36,
            "primary_color": "&H0000FFFF",  # Blue
            "outline_color": "&HFF000000",  # Black
            "back_color": "&H80FFFFFF",     # Semi-transparent white
            "bold": 1,
            "outline": 2.0,
            "shadow": 1.0,
            "alignment": 8,  # Bottom center
            "margin_v": 100
        }
        
        success, output_file = add_captions(
            video_path=self.test_video,
            transcript_path=self.test_transcript,
            output_path=self.output_path,
            custom_style=custom_style
        )
        
        assert success is True
        assert os.path.exists(output_file)
    
    def test_add_captions_with_line_wrapping(self):
        """Test caption overlay with different line wrapping settings."""
        # Test with very short line length to force wrapping
        success, output_file = add_captions(
            video_path=self.test_video,
            transcript_path=self.test_transcript,
            output_path=self.output_path,
            max_chars_per_line=10,
            line_spacing=15
        )
        
        assert success is True
        assert os.path.exists(output_file)
    
    def test_add_captions_with_fade_effects(self):
        """Test caption overlay with fade effects."""
        success, output_file = add_captions(
            video_path=self.test_video,
            transcript_path=self.test_transcript,
            output_path=self.output_path,
            fade_duration=0.5  # Half-second fade in/out
        )
        
        assert success is True
        assert os.path.exists(output_file)
    
    def test_add_captions_missing_video(self):
        """Test error handling for missing video file."""
        with pytest.raises(FileNotFoundError):
            add_captions(
                video_path="nonexistent_video.mp4",
                transcript_path=self.test_transcript,
                output_path=self.output_path
            )
    
    def test_add_captions_missing_transcript(self):
        """Test error handling for missing transcript file."""
        with pytest.raises(FileNotFoundError) as exc_info:
            add_captions(
                video_path=self.test_video,
                transcript_path="nonexistent_transcript.json",
                output_path=self.output_path
            )
        
        assert "Transcript file not found" in str(exc_info.value)
    
    def test_add_captions_invalid_style_preset(self):
        """Test error handling for invalid style preset."""
        success, output_file = add_captions(
            video_path=self.test_video,
            transcript_path=self.test_transcript,
            output_path=self.output_path,
            style_preset="invalid_preset"  # Should fall back to default
        )
        
        # Should still succeed but use default style
        assert success is True
        assert os.path.exists(output_file)
    
    @patch('app.caption_overlay.run_ffmpeg_command')
    def test_add_captions_ffmpeg_failure(self, mock_run_ffmpeg):
        """Test error handling when FFmpeg fails."""
        # Mock FFmpeg to fail
        mock_run_ffmpeg.return_value = (False, "FFmpeg error: Failed to process video")
        
        success, error = add_captions(
            video_path=self.test_video,
            transcript_path=self.test_transcript,
            output_path=self.output_path
        )
        
        assert success is False
        assert "FFmpeg error" in error
        # Verify output file was cleaned up
        assert not os.path.exists(self.output_path)

if __name__ == "__main__":
    pytest.main(["-v", "--cov=app", "--cov-report=term-missing"])