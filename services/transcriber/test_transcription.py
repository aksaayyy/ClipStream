#!/usr/bin/env python3
"""
Test script for the ClipStream Transcription Service with SSL handling.
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.services.transcription_service import TranscriptionService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('transcription_test.log')
    ]
)
logger = logging.getLogger("transcription-test")

def test_transcription(service: TranscriptionService, audio_path: str, language: Optional[str] = None) -> Dict[str, Any]:
    """Test transcription with the given service and audio file."""
    logger.info(f"Testing transcription with file: {audio_path}")
    
    if not os.path.exists(audio_path):
        logger.error(f"Audio file not found: {audio_path}")
        return {"success": False, "error": f"File not found: {audio_path}"}
    
    try:
        # Test transcription
        result = service.transcribe(audio_path, language=language)
        
        if result["success"]:
            logger.info("Transcription successful!")
            logger.info(f"Detected language: {result['language']}")
            logger.info(f"Duration: {result['duration']:.2f} seconds")
            logger.info(f"Processing time: {result['processing_time']:.2f} seconds")
            logger.info(f"Transcript: {result['text']}")
            
            # Save full result to file
            output_file = f"{Path(audio_path).stem}_transcript.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            logger.info(f"Full transcript saved to: {output_file}")
        else:
            logger.error(f"Transcription failed: {result.get('error', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error during transcription test: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

def main():
    """Main function to run transcription tests."""
    parser = argparse.ArgumentParser(description="Test ClipStream Transcription Service")
    parser.add_argument("audio_file", help="Path to the audio file to transcribe")
    parser.add_argument("--language", "-l", help="Language code (e.g., 'en', 'es')")
    parser.add_argument("--model", "-m", default="base", 
                       help="Whisper model to use (tiny, base, small, medium, large)")
    
    args = parser.parse_args()
    
    logger.info(f"Starting transcription test with model: {args.model}")
    
    try:
        # Initialize the transcription service
        service = TranscriptionService(model_name=args.model)
        
        # Run the test
        result = test_transcription(service, args.audio_file, args.language)
        
        # Print the result
        print("\n" + "="*50)
        print("TRANSCRIPTION TEST RESULT")
        print("="*50)
        print(f"Success: {result['success']}")
        if not result["success"]:
            print(f"Error: {result.get('error', 'Unknown error')}")
        else:
            print(f"Language: {result.get('language', 'unknown')}")
            print(f"Duration: {result.get('duration', 0):.2f} seconds")
            print(f"Processing time: {result.get('processing_time', 0):.2f} seconds")
            print("\nTranscript:")
            print("-"*50)
            print(result.get('text', ''))
            print("-"*50)
        
        return 0 if result["success"] else 1
        
    except Exception as e:
        logger.error(f"Fatal error during test: {str(e)}", exc_info=True)
        print(f"\nERROR: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
