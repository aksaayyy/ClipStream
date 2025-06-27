#!/usr/bin/env python3
"""
Script to preprocess transcript files for the ClipStream analyzer service.

This script converts the transcript format from the transcriber service to the format
expected by the analyzer service.

Input format (from transcriber):
{
  "success": true,
  "transcript": [
    {"start": 0.0, "end": 10.58, "text": "..."},
    ...
  ]
}

Output format (for analyzer):
[
  {"start": 0.0, "end": 10.58, "text": "..."},
  ...
]
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Union

def load_transcript(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Load transcript from a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def preprocess_transcript(transcript_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract segments from transcript data."""
    if not isinstance(transcript_data, dict):
        raise ValueError("Transcript data must be a dictionary")
    
    if 'transcript' in transcript_data:
        return transcript_data['transcript']
    elif isinstance(transcript_data.get('segments'), list):
        return transcript_data['segments']
    elif isinstance(transcript_data, list):
        return transcript_data
    else:
        raise ValueError("Could not find transcript segments in the input data")

def save_transcript(segments: List[Dict[str, Any]], output_path: Union[str, Path]) -> None:
    """Save segments to a JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(segments, f, indent=2, ensure_ascii=False)

def main():
    parser = argparse.ArgumentParser(description='Preprocess transcript files for the analyzer service')
    parser.add_argument('input_file', help='Path to the input transcript file')
    parser.add_argument('-o', '--output', help='Output file path (default: <input_file>_preprocessed.json)')
    
    args = parser.parse_args()
    
    # Set default output filename if not provided
    if not args.output:
        input_path = Path(args.input_file)
        args.output = str(input_path.with_name(f"{input_path.stem}_preprocessed.json"))
    
    try:
        # Load and preprocess the transcript
        print(f"Loading transcript from {args.input_file}")
        transcript_data = load_transcript(args.input_file)
        segments = preprocess_transcript(transcript_data)
        
        # Save the preprocessed transcript
        print(f"Saving preprocessed transcript to {args.output}")
        save_transcript(segments, args.output)
        print(f"Successfully preprocessed transcript. {len(segments)} segments extracted.")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
