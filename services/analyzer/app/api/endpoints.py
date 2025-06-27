"""
API endpoints for the Clip Analyzer service.
"""
import os
import json
import logging
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any, Optional

from ..models import (
    TranscriptSegment, 
    AnalyzeRequest, 
    AnalyzeResponse,
    ClipSuggestion
)
from ..core.analyzer import ClipAnalyzer

# Set up logging
logger = logging.getLogger(__name__)
router = APIRouter()
analyzer = ClipAnalyzer()

# In-memory storage for demo purposes
# In production, this would be replaced with a database or file storage
_transcript_cache: Dict[str, List[Dict[str, Any]]] = {}

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_transcript(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Analyze a transcript and return the most engaging clips.
    
    This endpoint takes a transcript file name, loads it from the data directory,
    analyzes it to find the most engaging clips, and returns them along with
    scoring information.
    """
    try:
        logger.info(f"Analyzing transcript: {request.filename}")
        
        # In a real implementation, we would load the transcript from a file
        # For now, we'll use the in-memory cache or a sample transcript
        transcript = _transcript_cache.get(request.filename)
        
        if not transcript:
            # For demo purposes, use a sample transcript if not found in cache
            logger.warning(f"Transcript {request.filename} not found, using sample data")
            transcript = [
                {"start": 0.0, "end": 5.0, "text": "Welcome to our channel!"},
                {"start": 5.0, "end": 15.0, "text": "Today we're doing something crazy and you won't believe what happens next!"},
                {"start": 15.0, "end": 25.0, "text": "We're going to test some amazing new technology that will blow your mind."},
                {"start": 25.0, "end": 35.0, "text": "This is just some normal talking that's not very exciting."},
                {"start": 35.0, "end": 50.0, "text": "But wait until you see this incredible result! It's absolutely mind-blowing!"},
                {"start": 50.0, "end": 60.0, "text": "Thanks for watching, don't forget to like and subscribe!"}
            ]
        
        # Analyze the transcript
        result = analyzer.analyze_transcript(
            transcript=transcript,
            min_duration=request.min_clip_duration,
            max_duration=request.max_clip_duration,
            top_k=request.top_k,
            language=request.language
        )
        
        if 'error' in result:
            logger.error(f"Analysis failed: {result['error']}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['error']
            )
        
        return AnalyzeResponse(
            success=True,
            video=request.filename.replace('_transcript.json', ''),
            language=request.language,
            total_duration=result['total_duration'],
            recommended_clips=result['recommended_clips']
        )
        
    except Exception as e:
        logger.exception(f"Error analyzing transcript: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing transcript: {str(e)}"
        )

@router.post("/transcripts/{video_id}")
async def upload_transcript(video_id: str, segments: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Upload a transcript for a video.
    
    In a real implementation, this would save the transcript to persistent storage.
    For this demo, we'll just store it in memory.
    """
    try:
        # Validate the segments
        for segment in segments:
            if not all(key in segment for key in ['start', 'end', 'text']):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Each segment must have 'start', 'end', and 'text' fields"
                )
        
        # Store in cache (in production, this would be saved to a database or file)
        filename = f"{video_id}_transcript.json"
        _transcript_cache[filename] = segments
        
        logger.info(f"Uploaded transcript for video {video_id} with {len(segments)} segments")
        return {"status": "success", "message": f"Transcript for {video_id} uploaded successfully"}
    
    except Exception as e:
        logger.exception(f"Error uploading transcript: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading transcript: {str(e)}"
        )

@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
