import os
import json
import tempfile
import shutil
import subprocess
import logging
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List, Union

from .utils.ffmpeg_utils import (
    run_ffmpeg_command,
    DEFAULT_FFMPEG_TIMEOUT,
    get_video_duration as get_video_duration_util,
    check_ffmpeg_installed
)

logger = logging.getLogger(__name__)

# Default styles for different platforms
STYLE_PRESETS = {
    "youtube": {
        "fontname": "Roboto",
        "fontsize": 48,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H80000000",
        "back_color": "&H80000000",
        "border_style": 1,
        "outline": 1.5,
        "shadow": 1,
        "alignment": 2,  # Center
        "margin_v": 50,
        "margin_l": 20,
        "margin_r": 20,
        "wrap_style": 0,
        "bold": 0,
        "italic": 0,
        "underline": 0,
    },
    "tiktok": {
        "fontname": "ProximaNova-Bold",
        "fontsize": 54,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "back_color": "&H00000000",
        "border_style": 1,
        "outline": 3.0,
        "shadow": 1,
        "alignment": 2,  # Center
        "margin_v": 150,
        "margin_l": 30,
        "margin_r": 30,
        "wrap_style": 2,  # Smart wrapping
        "bold": 1,
        "italic": 0,
        "underline": 0,
    },
    "instagram": {
        "fontname": "InstagramSans-Bold",
        "fontsize": 52,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "back_color": "&H40000000",
        "border_style": 3,
        "outline": 2.0,
        "shadow": 0,
        "alignment": 2,  # Center
        "margin_v": 100,
        "margin_l": 40,
        "margin_r": 40,
        "wrap_style": 2,  # Smart wrapping
        "bold": 1,
        "italic": 0,
        "underline": 0,
    }
}

def add_captions(
    video_path: Union[str, Path],
    transcript_path: Union[str, Path],
    output_path: Union[str, Path],
    style_preset: str = "youtube",
    custom_style: Optional[Dict[str, Any]] = None,
    max_chars_per_line: int = 40,
    line_spacing: int = 10,
    fade_duration: float = 0.2,
    timeout: int = DEFAULT_FFMPEG_TIMEOUT,
    log_output: bool = True
) -> Tuple[bool, str]:
    """
    Add styled captions to a video using FFmpeg's subtitles filter with ASS/SSA format.
    
    Args:
        video_path: Path to the input video file
        transcript_path: Path to the transcript JSON file
        output_path: Path where the output video will be saved
        style_preset: Preset style name ('youtube', 'tiktok', 'instagram')
        custom_style: Optional dictionary to override style properties
        max_chars_per_line: Maximum characters per line before wrapping
        line_spacing: Additional spacing between lines (in pixels)
        fade_duration: Fade in/out duration in seconds
        timeout: Maximum time to wait for the operation to complete (in seconds)
        log_output: Whether to log the command output
        
    Returns:
        Tuple of (success: bool, output_path: str)
    """
    # Convert Path objects to strings
    video_path = str(video_path)
    transcript_path = str(transcript_path)
    output_path = Path(output_path)
    
    # Validate inputs
    if not os.path.isfile(video_path):
        error_msg = f"Video file not found: {video_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
        
    if not os.path.isfile(transcript_path):
        error_msg = f"Transcript file not found: {transcript_path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)
    
    # Check FFmpeg installation
    if not check_ffmpeg_installed():
        error_msg = "FFmpeg is not installed or not in PATH"
        logger.error(error_msg)
        return False, error_msg
    
    # Get style preset or default to YouTube
    style = STYLE_PRESETS.get(style_preset.lower(), STYLE_PRESETS["youtube"]).copy()
    
    # Apply custom style overrides if provided
    if custom_style:
        style.update(custom_style)
    
    # Create output directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert Path objects to strings
    video_path = str(video_path)
    transcript_path = str(transcript_path)
    output_path = Path(output_path)
    
    # Create output directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Use a temporary file for the ASS subtitle file
    with tempfile.NamedTemporaryFile(suffix='.ass', delete=False, mode='w', encoding='utf-8') as f:
        ass_file = f.name
        
        # Write ASS header with styles
        f.write(f"""[Script Info]
ScriptType: v4.00+

PlayResX: 1920
PlayResY: 1080
WrapStyle: {style['wrap_style']}
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayDepth: 0
Timer: 100.0000

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, \
Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, \
Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
""")
        
        # Write style definition
        f.write(
            'Style: Default,'
            f"{style['fontname']},"
            f"{style['fontsize']},"
            f"{style['primary_color']},&H000000FF,{style['outline_color']},{style['back_color']},"
            f"{style['bold']},{style['italic']},0,0,100,100,0,0,{style['border_style']},"
            f"{style['outline']},{style['shadow']},{style['alignment']},"
            f"{style['margin_l']},{style['margin_r']},{style['margin_v']},1\n\n"
        )
        
        # Write events header
        f.write("[Events]\n"
               "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        
        # Load transcript
        try:
            with open(transcript_path, 'r', encoding='utf-8') as t:
                transcript = json.load(t)
        except Exception as e:
            error_msg = f"Failed to load transcript: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
        
        # Process and write each caption
        for segment in transcript.get("segments", []):
            try:
                start = format_time(segment["start"])
                end = format_time(segment["end"])
                
                # Split text into lines with word wrapping
                words = segment["text"].split()
                lines = []
                current_line = []
                
                for word in words:
                    if sum(len(w) for w in current_line) + len(current_line) + len(word) <= max_chars_per_line:
                        current_line.append(word)
                    else:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                if current_line:
                    lines.append(' '.join(current_line))
                
                # Format text with line breaks and effects
                text = '\\N'.join(lines)
                
                # Add fade effects if duration is sufficient
                fade_in = f"\\fade(255, 100, {int(fade_duration * 1000)},0,{int(fade_duration * 1000) // 2},0,0)" if segment["end"] - segment["start"] > fade_duration * 2 else ""
                fade_out = f"\\fade(255, 0, {int((segment['end'] - segment['start'] - fade_duration) * 1000)},{int(fade_duration * 1000)},{int(segment['end'] * 1000)},0,0)" if segment["end"] - segment["start"] > fade_duration * 2 else ""
                
                # Write the caption event
                f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{fade_in}{fade_out}{text}\\N")
            except Exception as e:
                logger.warning(f"Error processing caption segment: {e}", exc_info=True)
                continue  # Skip this segment but continue with others
    
    try:
        # Build FFmpeg command with proper escaping
        # First, escape the ASS file path for FFmpeg
        escaped_ass_file = str(ass_file).replace(':', '\\:')
        
        # Build the FFmpeg command
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file if it exists
            '-i', str(video_path),  # Input video
            '-vf', f"subtitles={escaped_ass_file}:force_style='FontName={style['fontname']},FontSize={style['fontsize']},PrimaryColour={style['primary_color']},OutlineColour={style['outline_color']},BackColour={style['back_color']},Bold={style['bold']},Italic={style['italic']},BorderStyle={style['border_style']},Outline={style['outline']},Shadow={style['shadow']},Alignment={style['alignment']},MarginL={style['margin_l']},MarginR={style['margin_r']},MarginV={style['margin_v']},Spacing={line_spacing}'",
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',  # Slightly lower quality for faster processing
            '-c:a', 'aac',
            '-b:a', '192k',
            '-movflags', '+faststart',
            str(output_path)
        ]
        
        # Log the command (without the full path to the temporary file)
        safe_cmd = ' '.join(cmd[:4] + ['[FILTER]'] + cmd[5:])
        logger.info(f"Running FFmpeg command: {safe_cmd}")
        
        # Run the FFmpeg command with our utility function
        success, output = run_ffmpeg_command(
            cmd,
            timeout=timeout,
            description=f"add_captions ({style_preset} style)"
        )
        
        if success:
            logger.info(f"Successfully added captions to {output_path}")
            return True, str(output_path)
        else:
            # Clean up the output file if it was partially created
            if output_path.exists():
                try:
                    output_path.unlink()
                    logger.debug(f"Removed partially created output file: {output_path}")
                except OSError as e:
                    logger.warning(f"Failed to remove output file {output_path}: {e}")
            return False, output
            
    except Exception as e:
        error_msg = f"Error adding captions: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg
        
    finally:
        # Clean up the temporary ASS file
        try:
            if os.path.exists(ass_file):
                os.remove(ass_file)
                logger.debug(f"Removed temporary file: {ass_file}")
        except Exception as e:
            logger.warning(f"Failed to remove temporary file {ass_file}: {e}", exc_info=True)

def format_time(seconds: float) -> str:
    """Convert seconds to ASS time format (H:MM:SS.mm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    return f"{hours}:{minutes:02d}:{seconds:05.2f}"

def get_supported_fonts() -> List[str]:
    """
    Get a list of system fonts that can be used for subtitles.
    Requires fontconfig to be installed on the system.
    """
    try:
        result = subprocess.run(
            ['fc-list', ':', 'family', 'style'],
            capture_output=True,
            text=True,
            check=True
        )
        # Parse font list and remove duplicates
        fonts = set()
        for line in result.stdout.split('\n'):
            if ':' in line:
                font = line.split(':')[0].strip()
                if font and not font.startswith('.'):  # Skip hidden files
                    fonts.add(font)
        return sorted(list(fonts))
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("Could not list system fonts. 'fontconfig' may not be installed.")
        return []

def escape_text(text: str) -> str:
    """Escape special characters in SRT text"""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
