"""
Data models for the Clip Analyzer service.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class TranscriptSegment(BaseModel):
    """Represents a single segment of a transcript."""
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Transcript text")

class ClipSuggestion(BaseModel):
    """Represents a suggested clip from the transcript."""
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Transcript text")
    score: float = Field(..., description="Clip score (0.0 to 1.0)")
    reason: str = Field(..., description="Reason for selection")

class AnalyzeRequest(BaseModel):
    """Request model for the analyze endpoint."""
    filename: str = Field(..., description="Name of the transcript file")
    min_clip_duration: float = Field(10.0, description="Minimum clip duration in seconds")
    max_clip_duration: float = Field(60.0, description="Maximum clip duration in seconds")
    top_k: int = Field(3, description="Number of top clips to return")
    language: str = Field("en", description="Language code for analysis")

class AnalyzeResponse(BaseModel):
    """Response model for the analyze endpoint."""
    success: bool = Field(..., description="Whether the analysis was successful")
    video: str = Field(..., description="Name of the video file")
    language: str = Field(..., description="Language code used for analysis")
    total_duration: str = Field(..., description="Total duration of the video (HH:MM:SS)")
    recommended_clips: List[ClipSuggestion] = Field(..., description="List of recommended clips")
    error: Optional[str] = Field(None, description="Error message if analysis failed")
