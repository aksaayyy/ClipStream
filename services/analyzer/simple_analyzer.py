#!/usr/bin/env python3
"""
Simple Clip Analyzer Service

A lightweight version of the analyzer that works with minimal dependencies.
"""
import os
import json
import random
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from loguru import logger

# Configure logging
logger.remove()
logger.add(
    "analyzer.log",
    rotation="10 MB",
    retention="10 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

# Initialize FastAPI app
app = FastAPI(
    title="ClipStream Analyzer Service",
    description="Lightweight service for analyzing video transcripts",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str

class AnalyzeRequest(BaseModel):
    filename: str = Field(..., description="Name of the transcript file")
    min_clip_duration: float = Field(10.0, description="Minimum clip duration in seconds")
    max_clip_duration: float = Field(60.0, description="Maximum clip duration in seconds")
    top_k: int = Field(3, description="Number of top clips to return")
    language: str = Field("en", description="Language code for analysis")

class ClipSuggestion(BaseModel):
    start: float
    end: float
    text: str
    score: float
    reason: str

class AnalyzeResponse(BaseModel):
    success: bool
    video: str
    language: str
    total_duration: str
    recommended_clips: List[ClipSuggestion]
    error: Optional[str] = None

# Analyzer class
class SimpleAnalyzer:
    def __init__(self):
        self.hook_phrases = [
            "you won't believe", "this is why", "what happened next", "watch what happens",
            "I was shocked when", "wait till you see", "here's the thing", "the truth about",
            "they didn't expect this", "what happened was"
        ]
        self.emotional_words = [
            "amazing", "unbelievable", "incredible", "shocking", "mind-blowing",
            "hilarious", "crazy", "insane", "epic", "legendary", "emotional",
            "heartbreaking", "tears", "crying", "laughing", "dying"
        ]
    
    def analyze_transcript(self, transcript: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze a transcript and return the top clips."""
        if not isinstance(transcript, list):
            return {"error": "Invalid transcript format. Expected a list of segments."}
        
        # Score each segment
        scored_segments = []
        for segment in transcript:
            if not all(key in segment for key in ['start', 'end', 'text']):
                continue
                
            score = self._score_segment(segment)
            scored_segments.append({
                **segment,
                'score': round(score, 2),
                'duration': round(segment['end'] - segment['start'], 2)
            })
        
        # Sort by score and get top clips
        scored_segments.sort(key=lambda x: x['score'], reverse=True)
        
        # Select non-overlapping top clips
        selected_clips = self._select_non_overlapping_clips(scored_segments)
        
        # Calculate total duration
        total_duration = self._calculate_total_duration(transcript)
        
        return {
            'success': True,
            'recommended_clips': selected_clips,
            'total_duration': total_duration
        }
    
    def _score_segment(self, segment: Dict[str, Any]) -> float:
        """Score a single transcript segment."""
        text = segment['text'].lower()
        score = 0.0
        
        # Check for hook phrases
        for phrase in self.hook_phrases:
            if phrase in text:
                score += 0.4  # Higher weight for hooks
                break
        
        # Check for emotional words
        emotion_count = sum(1 for word in self.emotional_words if word in text)
        score += min(0.3, emotion_count * 0.1)  # Cap emotional score at 0.3
        
        # Score based on length (10-30 seconds is ideal)
        duration = segment['end'] - segment['start']
        if 10 <= duration <= 30:
            score += 0.2
        elif duration < 10:
            score += (duration / 10.0) * 0.2
        else:
            score += max(0, 0.2 - (duration - 30) * 0.01)
        
        # Add some randomness to differentiate segments
        score = min(1.0, score + random.uniform(0, 0.1))
        
        return score
    
    def _select_non_overlapping_clips(self, segments: List[Dict[str, Any]], 
                                     max_clips: int = 5) -> List[Dict[str, Any]]:
        """Select non-overlapping clips from scored segments."""
        selected = []
        used_timestamps = []
        
        for segment in segments:
            # Skip segments that are too short
            if segment['duration'] < 5.0:
                continue
                
            # Check for overlap with already selected clips
            overlap = False
            for used_start, used_end in used_timestamps:
                if (segment['start'] <= used_end and segment['end'] >= used_start):
                    overlap = True
                    break
            
            if not overlap:
                selected.append({
                    'start': round(segment['start'], 1),
                    'end': round(segment['end'], 1),
                    'text': segment['text'],
                    'score': segment['score'],
                    'reason': self._generate_reason(segment)
                })
                used_timestamps.append((segment['start'], segment['end']))
                
                # Stop if we have enough clips
                if len(selected) >= max_clips:
                    break
        
        return selected
    
    def _generate_reason(self, segment: Dict[str, Any]) -> str:
        """Generate a human-readable reason for clip selection."""
        text = segment['text'].lower()
        reasons = []
        
        if any(hook in text for hook in self.hook_phrases):
            reasons.append("contains engaging hook")
            
        emotion_count = sum(1 for word in self.emotional_words if word in text)
        if emotion_count >= 2:
            reasons.append("emotional content")
            
        duration = segment['end'] - segment['start']
        if duration > 20:
            reasons.append("detailed explanation")
        elif duration < 10:
            reasons.append("concise delivery")
            
        return ", ".join(reasons) if reasons else "potentially engaging content"
    
    def _calculate_total_duration(self, transcript: List[Dict[str, Any]]) -> str:
        """Calculate and format total duration from transcript."""
        if not transcript:
            return "00:00:00"
            
        total_seconds = max(segment['end'] for segment in transcript)
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

# Initialize analyzer
analyzer = SimpleAnalyzer()

# API Endpoints
@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}

@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
async def analyze_transcript(request: AnalyzeRequest) -> Dict[str, Any]:
    """Analyze a transcript and return the most engaging clips."""
    try:
        # In a real implementation, we would load the transcript from a file
        # For now, we'll use a sample transcript
        sample_transcript = [
            {"start": 0.0, "end": 5.0, "text": "Welcome to our channel!"},
            {"start": 5.0, "end": 15.0, "text": "Today we're doing something crazy and you won't believe what happens next!"},
            {"start": 15.0, "end": 25.0, "text": "We're going to test some amazing new technology that will blow your mind."},
            {"start": 25.0, "end": 35.0, "text": "This is just some normal talking that's not very exciting."},
            {"start": 35.0, "end": 50.0, "text": "But wait until you see this incredible result! It's absolutely mind-blowing!"},
            {"start": 50.0, "end": 60.0, "text": "Thanks for watching, don't forget to like and subscribe!"}
        ]
        
        # Analyze the transcript
        result = analyzer.analyze_transcript(sample_transcript)
        
        if 'error' in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['error']
            )
        
        return {
            'success': True,
            'video': request.filename.replace('_transcript.json', ''),
            'language': request.language,
            'total_duration': result['total_duration'],
            'analyzed_at': datetime.utcnow().isoformat(),
            'recommended_clips': result['recommended_clips'][:request.top_k]
        }
        
    except Exception as e:
        logger.error(f"Error analyzing transcript: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing transcript: {str(e)}"
        )

# Error handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": exc.errors()},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("simple_analyzer:app", host="0.0.0.0", port=5003, reload=True)
