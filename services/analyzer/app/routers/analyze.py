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
    logger.info(f"Received analyze request: filename={request.filename}, segments_provided={request.segments is not None}")
    
    # Validate that either filename or segments is provided
    if request.filename is None and request.segments is None:
        error_msg = "Either 'filename' or 'segments' must be provided in the request"
        logger.error(error_msg)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    try:
        # Handle direct transcript data
        if request.segments is not None:
            logger.info("Processing direct transcript segments from request")
            # Use a temporary file path for direct transcript data
            transcript_path = None
            segments = request.segments
            
            logger.info(f"Segments type: {type(segments)}")
            if isinstance(segments, dict):
                logger.info(f"Segments dict keys: {segments.keys()}")
                if 'transcript' in segments:
                    logger.info(f"Found 'transcript' key, using it for segments")
                    segments = segments['transcript']
                    logger.info(f"Transcript type after extraction: {type(segments)}")
                
            # Validate segments format - handle both list of segments and dict with 'transcript' key
            if not isinstance(segments, list):
                error_msg = f"Expected segments to be a list, got {type(segments).__name__}"
                logger.error(error_msg)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_msg
                )
                
            # Log first segment for debugging
            if segments and len(segments) > 0:
                logger.info(f"First segment type: {type(segments[0])}")
                logger.info(f"First segment keys: {segments[0].keys() if isinstance(segments[0], dict) else 'N/A'}")
            
            # Validate each segment has required fields
            for i, seg in enumerate(segments):
                if not isinstance(seg, dict):
                    error_msg = f"Segment at index {i} is not a dictionary"
                    logger.error(error_msg)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=error_msg
                    )
                missing = [f for f in ['start', 'end', 'text'] if f not in seg]
                if missing:
                    error_msg = f"Segment at index {i} is missing required fields: {', '.join(missing)}"
                    logger.error(error_msg)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=error_msg
                    )
        else:
            # Handle file-based transcript
            transcript_path = os.path.join("/data/transcripts", request.filename)
            logger.info(f"Loading transcript from file: {transcript_path}")
            
            # Check if file exists and is accessible
            try:
                if not os.path.exists(transcript_path):
                    error_msg = f"Transcript file not found: {transcript_path}"
                    logger.error(error_msg)
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=error_msg
                    )
                
                if not os.access(transcript_path, os.R_OK):
                    error_msg = f"No read permission for transcript file: {transcript_path}"
                    logger.error(error_msg)
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=error_msg
                    )
                
                # Log file stats for debugging
                file_size = os.path.getsize(transcript_path)
                logger.info(f"Transcript file exists and is readable. Size: {file_size} bytes")
                
                # Try to read and parse the file to validate JSON format
                try:
                    with open(transcript_path, 'r', encoding='utf-8') as f:
                        transcript_content = f.read()
                        logger.info(f"Successfully read {len(transcript_content)} bytes from transcript file")
                        
                        # Try to parse the JSON to validate
                        import json
                        parsed = json.loads(transcript_content)
                        logger.info(f"Successfully parsed JSON from file. Type: {type(parsed)}")
                        
                        if isinstance(parsed, dict):
                            logger.info(f"Transcript JSON keys: {list(parsed.keys())}")
                            if 'transcript' in parsed:
                                transcript_segments = parsed['transcript']
                                logger.info(f"Found 'transcript' key with {len(transcript_segments) if isinstance(transcript_segments, list) else 'non-list'} value")
                                if isinstance(transcript_segments, list) and transcript_segments:
                                    first_seg = transcript_segments[0]
                                    logger.info(f"First segment type: {type(first_seg)}")
                                    if isinstance(first_seg, dict):
                                        logger.info(f"First segment keys: {list(first_seg.keys())}")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from {transcript_path}: {str(e)}")
                    # Log first 200 chars of the file for debugging
                    sample = transcript_content[:200] if 'transcript_content' in locals() else 'N/A'
                    logger.error(f"First 200 chars of file: {sample}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid JSON in transcript file: {str(e)}"
                    )
                except Exception as e:
                    logger.error(f"Error reading/parsing transcript file: {str(e)}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Error processing transcript file: {str(e)}"
                    )
                
            except HTTPException:
                raise  # Re-raise HTTP exceptions
            except Exception as e:
                logger.error(f"Unexpected error accessing transcript file: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error accessing transcript file: {str(e)}"
                )
            
            # Log file contents for debugging
            try:
                with open(transcript_path, 'r') as f:
                    content = f.read(1000)  # Read first 1000 chars for logging
                    logger.info(f"Transcript file content (first 1000 chars): {content}")
            except Exception as e:
                logger.warning(f"Could not read transcript file for logging: {str(e)}")
                
            segments = None
        
        # Log analysis parameters
        logger.info(f"Starting analysis with params: min_dur={request.min_clip_duration}, max_dur={request.max_clip_duration}, top_k={request.top_k}, lang={request.language}")
        
        try:
            # Analyze the transcript
            result = await analyzer.analyze(
                transcript_path=transcript_path,
                segments=segments,
                min_clip_duration=request.min_clip_duration,
                max_clip_duration=request.max_clip_duration,
                top_k=request.top_k,
                language=request.language
            )
            logger.info(f"Analysis completed successfully, found {len(result.get('recommended_clips', []))} clips")
        except Exception as e:
            logger.error(f"Error in analyzer.analyze: {str(e)}", exc_info=True)
            raise
        
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
