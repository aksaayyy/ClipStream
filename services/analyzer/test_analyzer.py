#!/usr/bin/env python3
"""
Test script for the Clip Analyzer service.

This script demonstrates how to use the AnalyzerService to analyze a transcript
and get the most engaging video clips.
"""
import os
import sys
import json
import asyncio
from pathlib import Path
from loguru import logger

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent / "app"))
from services.analyzer_service import AnalyzerService

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
)

# Sample transcript for testing
SAMPLE_TRANSCRIPT = [
    {"start": 0.0, "end": 5.0, "text": "Welcome to our channel!"},
    {"start": 5.0, "end": 15.0, "text": "Today we're doing something crazy and you won't believe what happens next!"},
    {"start": 15.0, "end": 25.0, "text": "We're going to test some amazing new technology that will blow your mind."},
    {"start": 25.0, "end": 35.0, "text": "This is just some normal talking that's not very exciting."},
    {"start": 35.0, "end": 50.0, "text": "But wait until you see this incredible result! It's absolutely mind-blowing!"},
    {"start": 50.0, "end": 60.0, "text": "Thanks for watching, don't forget to like and subscribe!"}
]

async def main():
    """Run the analyzer service test."""
    logger.info("Starting Clip Analyzer test...")
    
    # Create a temporary transcript file
    os.makedirs("test_data", exist_ok=True)
    transcript_path = "test_data/sample_transcript.json"
    
    with open(transcript_path, "w", encoding="utf-8") as f:
        json.dump(SAMPLE_TRANSCRIPT, f, indent=2)
    
    try:
        # Initialize the analyzer service
        analyzer = AnalyzerService()
        
        # Analyze the transcript
        logger.info(f"Analyzing transcript: {transcript_path}")
        result = await analyzer.analyze(
            transcript_path=transcript_path,
            min_clip_duration=5.0,
            max_clip_duration=30.0,
            top_k=3
        )
        
        # Print the results
        print("\n=== Analysis Results ===")
        print(f"Video: {result['video']}")
        print(f"Language: {result['language']}")
        print(f"Total Duration: {result['total_duration']}")
        print("\nTop Clips:")
        
        for i, clip in enumerate(result['recommended_clips'], 1):
            print(f"\nClip {i} (Score: {clip['score']:.2f}):")
            print(f"  Time: {clip['start']:.1f}s - {clip['end']:.1f}s")
            print(f"  Reason: {clip['reason']}")
            print(f"  Text: {clip['text']}")
        
        logger.success("Analysis completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}")
        raise
    finally:
        # Clean up
        if os.path.exists(transcript_path):
            os.remove(transcript_path)

if __name__ == "__main__":
    asyncio.run(main())
