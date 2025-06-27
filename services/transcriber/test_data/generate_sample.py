#!/usr/bin/env python3
"""
Script to generate a sample audio file for testing the transcriber service.
"""

from gtts import gTTS
import os

def generate_sample_audio():
    """Generate a sample audio file with test speech."""
    # Sample text to convert to speech
    text = """
    This is a sample audio file for testing the ClipStream transcriber service. 
    The quick brown fox jumps over the lazy dog. 
    This audio is approximately 5 seconds long.
    """
    
    # Create output directory if it doesn't exist
    os.makedirs("output", exist_ok=True)
    
    # Generate speech
    tts = gTTS(text=text, lang='en', slow=False)
    output_file = os.path.join("output", "sample.mp3")
    tts.save(output_file)
    
    print(f"Generated sample audio file: {os.path.abspath(output_file)}")

if __name__ == "__main__":
    generate_sample_audio()
