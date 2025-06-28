#!/usr/bin/env python3
"""
ClipStream Video Processor

A user-friendly CLI tool to process YouTube videos into viral clips.
"""

import os
import sys
import json
import time
import glob
import uuid
import shutil
import argparse
import subprocess
from typing import Dict, List, Optional, Any
import requests

# Configure the base URLs for the services
SERVICES = {
    'yt_fetcher': 'http://localhost:8001',
    'transcriber': 'http://localhost:5002',
    'analyzer': 'http://localhost:5003',
    'renderer': 'http://localhost:5004'
}

def print_header():
    """Print a nice header."""
    header = """
============================================================
                  CLIPSTREAM VIDEO PROCESSOR                
                 From YouTube to Viral Clips                
============================================================
"""
    print(header)

def ensure_output_dir():
    """Ensure the output directory exists."""
    os.makedirs('output', exist_ok=True)

def download_video(youtube_url: str) -> Dict[str, Any]:
    """Download a YouTube video using the yt-fetcher service."""
    print(f"\n📥 Downloading video from: {youtube_url}")
    
    try:
        response = requests.post(
            f"{SERVICES['yt_fetcher']}/fetch",
            json={"url": youtube_url},
            timeout=300  # 5 minute timeout
        )
        
        print(f"Response status code: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response content: {response.text[:100]}...")
        
        result = response.json()
        print("Parsed response:", json.dumps(result, indent=2, ensure_ascii=False)[:500] + "...")
        
        if result.get('success'):
            # The file is already in the shared volume, just return the path
            # The path from the container needs to be mapped to the host path
            container_path = result['path']
            
            # The container's /data is mounted to ./data on the host
            # So we need to convert /data/... to ./data/...
            if container_path.startswith('/data/'):
                local_path = os.path.join('.', container_path[1:])  # Convert /data/... to ./data/...
            else:
                local_path = os.path.join('data', 'downloads', os.path.basename(container_path))
            
            # Ensure the local downloads directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            print(f"📊 File will be available at: {local_path}")
            
            # Store both the container and local paths in the result
            result['container_path'] = container_path
            result['local_path'] = local_path
            
            # Verify the file exists at the local path
            if os.path.exists(local_path):
                print(f"✅ File found at: {local_path}")
                print(f"📏 File size: {os.path.getsize(local_path) / (1024*1024):.2f} MB")
            else:
                print(f"⚠️  File not found at: {local_path}")
                print("Please check if the volume is properly mounted in docker-compose.yml")
            
            return result
        else:
            print(f"❌ Error downloading video: {result.get('error', 'Unknown error')}")
            sys.exit(1)
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error connecting to yt-fetcher service: {str(e)}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse response from yt-fetcher: {str(e)}")
        sys.exit(1)

def split_video(video_path: str, chunk_duration: int = 600) -> str:
    """
    Split video into smaller chunks for processing.
    
    Args:
        video_path: Path to the video file (can be either container or host path)
        chunk_duration: Duration of each chunk in seconds
        
    Returns:
        str: Path to the directory containing the chunks
    """
    print(f"\n✂️  Splitting video into {chunk_duration}-second chunks...")
    
    # Create chunks directory if it doesn't exist
    chunks_dir = os.path.join('data', 'chunks')
    os.makedirs(chunks_dir, exist_ok=True)
    
    # Generate a unique prefix for the output files
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    output_pattern = os.path.join(chunks_dir, f"{base_name}_%03d.mp4")
    
    # Check if the input file exists
    if not os.path.exists(video_path):
        print(f"❌ Input video file not found: {video_path}")
        print("Current working directory:", os.getcwd())
        print("Directory contents:", os.listdir(os.path.dirname(video_path) or '.'))
        sys.exit(1)
    
    # Use ffmpeg to split the video
    cmd = [
        'ffmpeg',
        '-i', video_path,
        '-c', 'copy',  # Use stream copy mode (no re-encoding)
        '-f', 'segment',
        '-segment_time', str(chunk_duration),
        '-reset_timestamps', '1',
        output_pattern
    ]
    
    try:
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("ffmpeg output:", result.stdout)
        if result.stderr:
            print("ffmpeg stderr:", result.stderr)
        
        # Get the list of generated chunks
        chunk_files = sorted(glob.glob(os.path.join(chunks_dir, f"{base_name}_*.mp4")))
        if not chunk_files:
            print(f"❌ No chunk files were created. Check ffmpeg output above.")
            print(f"Tried to create files matching: {os.path.join(chunks_dir, f'{base_name}_*.mp4')}")
            print("Chunks directory contents:", os.listdir(chunks_dir))
            sys.exit(1)
            
        print(f"✅ Successfully split video into {len(chunk_files)} chunks")
        for i, chunk in enumerate(chunk_files, 1):
            print(f"  {i}. {os.path.basename(chunk)} ({(os.path.getsize(chunk) / (1024*1024)):.2f} MB)")
        
        return chunks_dir
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error splitting video: {str(e)}")
        print("Command output:", e.stdout)
        print("Command error:", e.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error in split_video: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        return duration
        
    except (subprocess.CalledProcessError, ValueError) as e:
        print(f"⚠️  Could not get video duration: {str(e)}")
        return 0

def transcribe_audio(video_path: str, video_duration_sec: Optional[float] = None) -> Dict[str, Any]:
    """
    Transcribe the audio from a video file using the transcriber service.
    
    Args:
        video_path: Path to the video file
        video_duration_sec: Duration of the video in seconds (optional, will be calculated if not provided)
        
    Returns:
        dict: Transcription result with segments and metadata
    """
    print(f"\n🔍 Transcribing audio from: {os.path.basename(video_path)}")
    
    # Calculate duration if not provided
    if video_duration_sec is None:
        video_duration_sec = get_video_duration(video_path)
    
    # First, check if we have a local transcript file
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    transcript_file = os.path.join('data', 'transcripts', f"{base_name}.json")
    
    if os.path.exists(transcript_file):
        print(f"📄 Found existing transcript: {transcript_file}")
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                transcript = json.load(f)
            
            # Verify the transcript has the expected structure
            if 'transcript' in transcript and isinstance(transcript['transcript'], list):
                print("✅ Using cached transcript")
                return transcript
            else:
                print("⚠️  Cached transcript has unexpected format, regenerating...")
        except Exception as e:
            print(f"⚠️  Error reading cached transcript: {e}, regenerating...")
    
    # If we get here, we need to transcribe the audio
    print("🎙️  Sending audio for transcription...")
    
    # Split the video into smaller chunks if it's too long
    max_chunk_duration = 300  # 5 minutes per chunk
    if video_duration_sec > max_chunk_duration * 1.5:  # Add some buffer
        print(f"⏳ Video is long ({video_duration_sec/60:.1f} minutes), splitting into chunks...")
        chunks_dir = split_video(video_path, max_chunk_duration)
        
        # Get list of chunk files
        chunk_files = sorted(glob.glob(os.path.join(chunks_dir, '*.mp4')))
        print(f"✅ Split into {len(chunk_files)} chunks")
        
        # Transcribe each chunk
        all_segments = []
        total_duration = 0.0
        
        for i, chunk_file in enumerate(chunk_files, 1):
            print(f"\n🔍 Processing chunk {i}/{len(chunk_files)}: {os.path.basename(chunk_file)}")
            chunk_duration = get_video_duration(chunk_file)
            
            # Transcribe the chunk with retry logic
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                try:
                    print(f"📤 Sending chunk {i} to transcriber service (attempt {attempt}/{max_retries})...")
                    # Send the chunk to the transcriber service
                    chunk_filename = os.path.basename(chunk_file)
                    print(f"🔊 Transcribing chunk {i} (this may take a few minutes)...")
                    response = requests.post(
                        f"{SERVICES['transcriber']}/api/v1/transcribe",
                        json={
                            "filename": chunk_filename,
                            "language": "hi",  # Assuming Hindi language
                            "model": "tiny"  # Using tiny model for faster transcription
                        },
                        timeout=900  # 15 minute timeout for transcription
                    )
                    
                    if response.status_code == 200:
                        chunk_result = response.json()
                        if chunk_result.get('success', False):
                            # Adjust timestamps for this chunk
                            for segment in chunk_result.get('transcript', []):
                                segment['start'] += total_duration
                                segment['end'] += total_duration
                                all_segments.append(segment)
                            
                            total_duration += chunk_duration
                            print(f"✅ Successfully transcribed chunk {i}")
                            break  # Success, exit retry loop
                        else:
                            error_msg = chunk_result.get('error', 'Unknown error')
                            print(f"❌ Error transcribing chunk {i}: {error_msg}")
                            if attempt == max_retries:
                                return {"success": False, "error": f"Failed to transcribe chunk {i} after {max_retries} attempts: {error_msg}"}
                    else:
                        print(f"❌ Error from transcriber service (chunk {i}): {response.status_code} - {response.text}")
                        if attempt == max_retries:
                            return {"success": False, "error": f"Transcriber service returned {response.status_code} after {max_retries} attempts"}
                
                except requests.exceptions.RequestException as e:
                    if attempt == max_retries:
                        print(f"❌ Network error transcribing chunk {i} after {max_retries} attempts: {str(e)}")
                        return {"success": False, "error": f"Network error after {max_retries} attempts: {str(e)}"}
                    print(f"⚠️  Network error (attempt {attempt}/{max_retries}), retrying in 5 seconds...")
                    time.sleep(5)  # Wait before retrying
                except Exception as e:
                    if attempt == max_retries:
                        print(f"❌ Unexpected error transcribing chunk {i} after {max_retries} attempts: {str(e)}")
                        return {"success": False, "error": f"Unexpected error after {max_retries} attempts: {str(e)}"}
                    print(f"⚠️  Error (attempt {attempt}/{max_retries}), retrying in 5 seconds...")
                    time.sleep(5)  # Wait before retrying
        
        # Combine all segments into a single transcript
        transcript = {
            "success": True,
            "transcript": all_segments,
            "language": "hi",  # Assuming Hindi
            "duration": total_duration,
            "duration_formatted": f"{int(total_duration // 60)}:{int(total_duration % 60):02d}",
            "file_path": transcript_file
        }
        
    else:
        # Transcribe the entire file at once with retry logic
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                print(f"📤 Sending to transcriber service (attempt {attempt}/{max_retries})...")
                # Send the file to the transcriber service
                with open(video_path, 'rb') as f:
                    files = {'file': (os.path.basename(video_path), f, 'video/mp4')}
                    response = requests.post(
                        f"{SERVICES['transcriber']}/api/v1/transcribe",
                        files=files,
                        data={"language": "hi"},  # Assuming Hindi language
                        timeout=300  # 5 minute timeout
                    )
                
                if response.status_code == 200:
                    transcript = response.json()
                    if transcript.get('success', False):
                        break  # Success, exit retry loop
                    else:
                        error_msg = transcript.get('error', 'Unknown error')
                        print(f"❌ Error from transcriber service: {error_msg}")
                        if attempt == max_retries:
                            return {"success": False, "error": f"Transcriber service reported an error after {max_retries} attempts: {error_msg}"}
                else:
                    print(f"❌ Error from transcriber service: {response.status_code} - {response.text}")
                    if attempt == max_retries:
                        return {"success": False, "error": f"Transcriber service returned {response.status_code} after {max_retries} attempts"}
                
            except requests.exceptions.RequestException as e:
                if attempt == max_retries:
                    print(f"❌ Network error after {max_retries} attempts: {str(e)}")
                    return {"success": False, "error": f"Network error after {max_retries} attempts: {str(e)}"}
                print(f"⚠️  Network error (attempt {attempt}/{max_retries}), retrying in 5 seconds...")
                time.sleep(5)  # Wait before retrying
            except Exception as e:
                if attempt == max_retries:
                    print(f"❌ Unexpected error after {max_retries} attempts: {str(e)}")
                    return {"success": False, "error": f"Unexpected error after {max_retries} attempts: {str(e)}"}
                print(f"⚠️  Error (attempt {attempt}/{max_retries}), retrying in 5 seconds...")
                time.sleep(5)  # Wait before retrying
    
    # Save the transcript to a file
    os.makedirs(os.path.dirname(transcript_file), exist_ok=True)
    with open(transcript_file, 'w', encoding='utf-8') as f:
        json.dump(transcript, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Transcription complete. Transcript saved to: {transcript_file}")
    return transcript

def analyze_transcript(transcript: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze the transcript to find viral clips."""
    print("\n🔍 Analyzing transcript for viral moments...")
    
    try:
        # Prepare the request payload according to the analyzer API spec
        payload = {
            "segments": transcript,
            "min_clip_duration": 10.0,
            "max_clip_duration": 60.0,
            "top_k": 5,
            "language": "en"
        }
        
        print(f"📊 Sending transcript with {len(transcript)} segments to analyzer...")
        
        # Increase timeout to 10 minutes and add retry logic
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                print(f"📤 Sending to analyzer service (attempt {attempt}/{max_retries})...")
                response = requests.post(
                    f"{SERVICES['analyzer']}/api/v1/analyze",
                    json=payload,
                    timeout=600  # 10 minute timeout
                )
                
                response.raise_for_status()
                result = response.json()
                
                if result.get('success'):
                    print(f"✅ Found {len(result.get('recommended_clips', []))} potential clips")
                    return result
                else:
                    error_msg = result.get('error', 'Unknown error')
                    print(f"❌ Error analyzing transcript: {error_msg}")
                    if attempt == max_retries:
                        return None
            except requests.exceptions.RequestException as e:
                if attempt == max_retries:
                    print(f"❌ Error connecting to analyzer service after {max_retries} attempts: {str(e)}")
                    return None
                print(f"⚠️  Attempt {attempt} failed, retrying in 5 seconds...")
                time.sleep(5)
        
        return None
            
    except Exception as e:
        print(f"❌ Unexpected error in analyze_transcript: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def render_clips(video_path: str, clips: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Render the video clips using the renderer service."""
    print("\n🎬 Rendering clips...")
    
    try:
        # Read the video file as binary
        with open(video_path, 'rb') as f:
            files = {
                'video': (os.path.basename(video_path), f, 'video/mp4')
            }
            
            # Send the request with the video file and clip data
            response = requests.post(
                f"{SERVICES['renderer']}/api/v1/render",
                files=files,
                data={
                    'clips': json.dumps(clips),
                    'output_dir': 'output'
                },
                timeout=1800  # 30 minute timeout for rendering
            )
        
        response.raise_for_status()
        result = response.json()
        
        if result.get('success'):
            print(f"✅ Successfully rendered {len(result.get('clips_rendered', []))} clips")
            return result
        else:
            print(f"❌ Error rendering clips: {result.get('error', 'Unknown error')}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error connecting to renderer service: {str(e)}")
        if hasattr(e, 'response') and e.response:
            print(f"Response status: {e.response.status_code}")
            print(f"Response content: {e.response.text}")
        return None


def process_video(youtube_url: str):
    """Process a YouTube video through the entire pipeline."""
    ensure_output_dir()
    
    # Step 1: Download the video
    print("\n🔍 Step 1/4: Downloading video...")
    download_result = download_video(youtube_url)
    
    # Extract the video path from the response
    video_path = download_result.get('local_path') or download_result.get('path')
    if not video_path:
        print("❌ Could not determine video path from download result")
        sys.exit(1)
    
    # Get video duration from the download result or calculate it
    duration_str = download_result.get('duration', '0:00')
    try:
        # Convert "HH:MM:SS" or "MM:SS" to seconds
        duration_parts = list(map(int, duration_str.split(':')))
        if len(duration_parts) == 3:  # HH:MM:SS
            duration_sec = duration_parts[0] * 3600 + duration_parts[1] * 60 + duration_parts[2]
        elif len(duration_parts) == 2:  # MM:SS
            duration_sec = duration_parts[0] * 60 + duration_parts[1]
        else:
            duration_sec = 0
    except (ValueError, AttributeError):
        duration_sec = 0
    
    print(f"📏 Video duration: {duration_sec} seconds")
    
    # Step 2: Transcribe the audio
    print("\n🔍 Step 2/4: Transcribing audio...")
    print(f"📂 Using video file: {video_path}")
    
    transcription_result = transcribe_audio(video_path, duration_sec)
    if not transcription_result or not transcription_result.get('success'):
        print("❌ Failed to transcribe audio")
        sys.exit(1)
    
    # Step 3: Analyze the transcript for viral moments
    print("\n🔍 Step 3/4: Analyzing transcript...")
    analysis_result = analyze_transcript(transcription_result['transcript'])
    if not analysis_result or not analysis_result.get('success'):
        print("❌ Failed to analyze transcript")
        sys.exit(1)
    
    # Step 4: Render the clips
    print("\n🔍 Step 4/4: Rendering clips...")
    render_result = render_clips(video_path, analysis_result.get('clips', []))
    if not render_result or not render_result.get('success'):
        print("❌ Failed to render clips")
        sys.exit(1)
    
    # Print summary
    print("\n" + "="*60)
    print("🎉 VIDEO PROCESSING COMPLETE!")
    print("="*60)
    
    print(f"\n📊 Summary:")
    print(f"- Video: {os.path.basename(video_path)}")
    print(f"- Duration: {duration_sec} seconds")
    print(f"- Transcript segments: {len(transcription_result.get('transcript', []))}")
    print(f"- Clips generated: {len(analysis_result.get('clips', []))}")
    
    if render_result.get('clips_rendered'):
        print("\n🎬 Rendered clips:")
        for i, clip in enumerate(render_result.get('clips_rendered', []), 1):
            print(f"  {i}. {clip}")
    else:
        print("\nNo clips were generated from the video.")

def main():
    parser = argparse.ArgumentParser(description='Process YouTube videos into viral clips.')
    parser.add_argument('url', help='YouTube URL to process')
    args = parser.parse_args()
    
    print_header()
    process_video(args.url)

if __name__ == "__main__":
    main()
