import os
import logging
import time
import ssl
import certifi
from typing import List, Dict, Any, Optional
from pathlib import Path
import whisper
import urllib.request
import tempfile
import shutil

# Patch SSL context to use certifi certificates
ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl._create_default_https_context = lambda: ssl_context

# Monkey patch urllib to use our SSL context
original_urlopen = urllib.request.urlopen

def patched_urlopen(*args, **kwargs):
    kwargs['context'] = ssl_context
    return original_urlopen(*args, **kwargs)

urllib.request.urlopen = patched_urlopen

logger = logging.getLogger("transcriber")

class TranscriptionService:
    def __init__(self, model_name: str = "base"):
        """
        Initialize the transcription service with a Whisper model.
        
        Args:
            model_name: Name of the Whisper model to use (tiny, base, small, medium, large)
        """
        self.model_name = model_name
        self.model = None
        self.load_model()
    
    def load_model(self):
        """
        Load the Whisper model with improved error handling and SSL verification.
        """
        try:
            logger.info(f"Loading Whisper model: {self.model_name}")
            start_time = time.time()
            
            # Create a temporary directory for model download
            with tempfile.TemporaryDirectory() as temp_dir:
                # Set environment variable to use our temp directory
                os.environ['TORCH_HOME'] = temp_dir
                
                try:
                    # First try with SSL verification
                    self.model = whisper.load_model(self.model_name, download_root=temp_dir)
                except Exception as e:
                    logger.warning(f"Failed to download with SSL verification: {str(e)}")
                    logger.info("Retrying with SSL verification disabled...")
                    
                    # If SSL verification fails, try with unverified context
                    unverified_ssl = ssl._create_unverified_context()
                    ssl._create_default_https_context = lambda: unverified_ssl
                    
                    try:
                        self.model = whisper.load_model(self.model_name, download_root=temp_dir)
                    except Exception as e2:
                        logger.error(f"Failed to load model even with unverified SSL: {str(e2)}")
                        logger.info("This might be due to network restrictions or SSL issues.")
                        logger.info("Please try manually downloading the model using the download_model.py script.")
                        raise RuntimeError(
                            "Failed to load Whisper model. "
                            "Please download the model manually using the download_model.py script "
                            "and ensure it's in the correct cache directory."
                        ) from e2
            
            load_time = time.time() - start_time
            logger.info(f"Successfully loaded model in {load_time:.2f} seconds")
            
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {str(e)}")
            logger.error("Please ensure you have a stable internet connection and sufficient disk space.")
            logger.error("You can also try downloading the model manually using the download_model.py script.")
            raise
    
    def transcribe(
        self, 
        audio_path: str, 
        language: Optional[str] = None,
        **transcribe_kwargs
    ) -> Dict[str, Any]:
        """
        Transcribe an audio file using Whisper with enhanced error handling.
        
        Args:
            audio_path: Path to the audio file to transcribe
            language: Language code (e.g., 'en', 'es', 'fr')
            **transcribe_kwargs: Additional arguments to pass to whisper's transcribe method
            
        Returns:
            Dictionary containing the transcription result or error information
            
        Raises:
            FileNotFoundError: If the audio file doesn't exist
            RuntimeError: If transcription fails
        """
        if not os.path.exists(audio_path):
            error_msg = f"Audio file not found: {audio_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
        
        if not self.model:
            error_msg = "Whisper model is not loaded. Please call load_model() first."
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        try:
            logger.info(f"Starting transcription for: {audio_path}")
            logger.debug(f"Language: {language or 'auto'}")
            start_time = time.time()
            
            # Default transcription parameters
            transcribe_params = {
                'audio': audio_path,
                'language': language,
                'fp16': False,  # Disable FP16 for better compatibility
                **transcribe_kwargs  # Allow overriding defaults
            }
            
            # Remove None values to use whisper's defaults
            transcribe_params = {k: v for k, v in transcribe_params.items() if v is not None}
            
            # Perform transcription
            result = self.model.transcribe(**transcribe_params)
            
            if not result or 'segments' not in result:
                raise RuntimeError("Transcription returned no results or invalid format")
            
            # Process segments into a cleaner format
            segments = []
            for segment in result.get("segments", []):
                try:
                    segments.append({
                        "start": float(segment.get("start", 0)),
                        "end": float(segment.get("end", 0)),
                        "text": str(segment.get("text", "")).strip()
                    })
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"Error processing segment: {e}")
                    continue
            
            # Get full text if available
            full_text = result.get("text", "")
            if not full_text and segments:
                full_text = " ".join(seg["text"] for seg in segments)
            
            transcription_time = time.time() - start_time
            logger.info(f"Transcription completed in {transcription_time:.2f} seconds")
            
            return {
                "success": True,
                "language": result.get("language", language or "unknown").lower(),
                "duration": float(result.get("duration", 0)),
                "segments": segments,
                "text": full_text.strip(),
                "processing_time": transcription_time
            }
            
        except Exception as e:
            error_msg = f"Transcription failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            return {
                "success": False,
                "error": error_msg,
                "language": language,
                "duration": 0,
                "segments": [],
                "text": "",
                "processing_time": time.time() - start_time if 'start_time' in locals() else 0
            }
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """Format duration in seconds to HH:MM:SS"""
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

# Global instance for easier import
transcription_service = TranscriptionService()
