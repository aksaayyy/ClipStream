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

from fastapi import UploadFile, File, Form

class TranscribeRequest(BaseModel):
    file: Optional[UploadFile] = None
    filename: Optional[str] = None
    language: Optional[str] = None
    model: Optional[str] = "base"
    
    class Config:
        arbitrary_types_allowed = True

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
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    model: Optional[str] = Form("base"),
    service: TranscriptionService = Depends(lambda: transcription_service)
):
    """
    Transcribe an audio/video file to text using Whisper.
    
    Args:
        file: The audio/video file to transcribe
        language: Optional language code (e.g., 'en', 'es', 'fr')
        model: Whisper model to use (tiny, base, small, medium, large)
        
    Returns:
        TranscribeResponse with transcript segments and metadata
    """
    # Create a temporary file to store the uploaded content
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or "")[1])
    
    try:
        # Save the uploaded file to a temporary location
        try:
            contents = await file.read()
            with open(temp_file.name, 'wb') as f:
                f.write(contents)
        except Exception as e:
            logger.error(f"Error saving uploaded file: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error processing uploaded file: {str(e)}"
            )
        
        # Create transcripts directory if it doesn't exist
        local_data_dir = os.getenv("LOCAL_DATA_DIR", "/app/data")
        transcripts_dir = os.path.join(local_data_dir, "transcripts")
        os.makedirs(transcripts_dir, exist_ok=True)
        
        # Generate output filename
        base_name = Path(file.filename or "audio").stem
        output_file = f"{base_name}.json"
        output_path = os.path.join(transcripts_dir, output_file)
        
        # Transcribe the audio
        result = service.transcribe(temp_file.name, language=language)
        
        if not result["success"]:
            error_msg = result.get("error", "Unknown error during transcription")
            logger.error(f"Transcription failed: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Transcription failed: {error_msg}"
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
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(response, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving transcript: {str(e)}")
            # Don't fail the request if we can't save the transcript file
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {str(e)}"
        )
    finally:
        # Clean up the temporary file
        try:
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
        except Exception as e:
            logger.warning(f"Error cleaning up temporary file: {str(e)}")
