from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import os

from app.services.analyzer_service import AnalyzerService

logger = logging.getLogger("analyzer")
router = APIRouter(prefix="/api/v1", tags=["analyze"])

class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str

class AnalyzeRequest(BaseModel):
    filename: Optional[str] = Field(
        None,
        description="Name of the transcript file in /data/transcripts/. Either filename or segments must be provided."
    )
    segments: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="List of transcript segments. Either filename or segments must be provided."
    )
    min_clip_duration: float = Field(10.0, description="Minimum clip duration in seconds")
    max_clip_duration: float = Field(60.0, description="Maximum clip duration in seconds")
    top_k: int = Field(5, description="Number of top clips to return")
    language: Optional[str] = Field("en", description="Language code for analysis")
    
    class Config:
        schema_extra = {
            "example": {
                "filename": "example_transcript.json",
                "min_clip_duration": 10.0,
                "max_clip_duration": 60.0,
                "top_k": 3,
                "language": "en"
            }
        }

class ClipSuggestion(BaseModel):
    start: float
    end: float
    text: str
    score: float
    reason: str

class AnalyzeResponse(BaseModel):
    success: bool
    video: Optional[str] = Field(
        None,
        description="Video filename if available, None for direct transcript analysis"
    )
    language: str
    total_duration: str
    recommended_clips: List[ClipSuggestion]
    error: Optional[str] = None

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_transcript(
    request: AnalyzeRequest,
    analyzer: AnalyzerService = Depends(AnalyzerService)
) -> Dict[str, Any]:
    """
    Analyze a transcript and identify the most viral-worthy moments.
    
    This endpoint can either:
    1. Load a transcript from a file in /data/transcripts/ (specify 'filename')
    2. Accept transcript data directly in the request (specify 'segments')
    
    Args:
        request: Analysis request parameters
        analyzer: Analyzer service instance
        
    Returns:
        Analysis results with top clips
    """
    # Validate that either filename or segments is provided
    if request.filename is None and request.segments is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'filename' or 'segments' must be provided in the request"
        )
    
    try:
        # Handle direct transcript data
        if request.segments is not None:
            # Use a temporary file path for direct transcript data
            transcript_path = None
            segments = request.segments
            
            # Validate segments format
            if not isinstance(segments, list) or not all(
                isinstance(seg, dict) and 'start' in seg and 'end' in seg and 'text' in seg
                for seg in segments
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid segments format. Each segment must have 'start', 'end', and 'text' fields"
                )
        else:
            # Handle file-based transcript
            transcript_path = os.path.join("/data/transcripts", request.filename)
            
            # Check if file exists
            if not os.path.exists(transcript_path):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Transcript file not found: {request.filename}"
                )
            segments = None
        
        # Analyze the transcript
        result = await analyzer.analyze(
            transcript_path=transcript_path,
            segments=segments,
            min_clip_duration=request.min_clip_duration,
            max_clip_duration=request.max_clip_duration,
            top_k=request.top_k,
            language=request.language
        )
        
        # Prepare output
        output = {
            'success': True,
            'video': request.filename if request.filename else None,
            'language': request.language or 'en',
            'total_duration': result.get("total_duration", "00:00"),
            'recommended_clips': [
                {
                    'start': clip.get('start', 0.0),
                    'end': clip.get('end', 0.0),
                    'text': clip.get('text', ''),
                    'score': clip.get('score', 0.0),
                    'reason': clip.get('reason', '')
                } for clip in result.get("recommended_clips", [])[:request.top_k]
            ]
        }
        
        return output
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing transcript: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing transcript: {str(e)}"
        )
