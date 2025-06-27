import os
import json
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services.transcription_service import transcription_service, TranscriptionService

logger = logging.getLogger("transcriber")

router = APIRouter(prefix="/api/v1", tags=["transcription"])

class TranscribeRequest(BaseModel):
    filename: str
    language: Optional[str] = None
    model: Optional[str] = "base"

class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str

class TranscribeResponse(BaseModel):
    success: bool
    transcript: List[TranscriptSegment]
    language: str
    duration: float
    duration_formatted: str
    file_path: Optional[str] = None
    error: Optional[str] = None

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    request: TranscribeRequest,
    service: TranscriptionService = Depends(lambda: transcription_service)
):
    """
    Transcribe an audio/video file to text using Whisper.
    
    Args:
        request: TranscribeRequest containing filename and optional parameters
        
    Returns:
        TranscribeResponse with transcript segments and metadata
    """
    try:
        # Get the path to the downloads directory from environment variable
        download_dir = os.getenv("DOWNLOAD_DIR", "/data/downloads")
        transcripts_dir = os.getenv("TRANSCRIPTS_DIR", "/data/transcripts")
        
        # Create transcripts directory if it doesn't exist
        os.makedirs(transcripts_dir, exist_ok=True)
        
        source_path = os.path.join(download_dir, request.filename)
        
        # Verify the file exists
        if not os.path.exists(source_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {request.filename}"
            )
        
        # Create a temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            # If the file is a video, we might need to extract audio first
            # For now, we'll assume the file is in a format Whisper can handle directly
            audio_path = source_path
            
            # Generate output filename
            base_name = Path(request.filename).stem
            output_file = f"{base_name}.json"
            output_path = os.path.join(transcripts_dir, output_file)
            
            # Transcribe the audio
            result = service.transcribe(audio_path, language=request.language)
            
            if not result["success"]:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Transcription failed: {result.get('error', 'Unknown error')}"
                )
            
            # Format the response
            response = {
                "success": True,
                "transcript": [
                    {
                        "start": seg["start"],
                        "end": seg["end"],
                        "text": seg["text"]
                    }
                    for seg in result["segments"]
                ],
                "language": result["language"],
                "duration": result["duration"],
                "duration_formatted": service.format_duration(result["duration"]),
                "file_path": output_path
            }
            
            # Save the transcript to a file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(response, f, ensure_ascii=False, indent=2)
            
            return response
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {str(e)}"
        )
