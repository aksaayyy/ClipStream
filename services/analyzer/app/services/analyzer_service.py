import os
import json
import re
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
from loguru import logger
from sentence_transformers import SentenceTransformer
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

# Download required NLTK data
nltk.download('vader_lexicon', quiet=True)

class AnalyzerService:
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        """Initialize the AnalyzerService with a sentence transformer model.
        
        Args:
            model_name: Name of the sentence transformer model to use
        """
        self.model_name = model_name
        self.model = None
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
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
    
    def load_model(self):
        """Load the sentence transformer model."""
        if self.model is None:
            logger.info(f"Loading sentence transformer model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
    
    def _score_segment(self, segment: Dict[str, Any]) -> float:
        """Score a single transcript segment.
        
        Args:
            segment: Dictionary containing 'start', 'end', and 'text' keys
            
        Returns:
            Float score between 0 and 1
        """
        text = segment['text'].lower()
        
        # Initialize scores
        scores = {
            'hook': 0.0,       # Presence of hook phrases
            'emotion': 0.0,    # Emotional content
            'pacing': 0.0,     # Words per second
            'length': 0.0,     # Segment duration (10-60s is ideal)
            'intensity': 0.0   # NLP intensity score
        }
        
        # 1. Check for hook phrases
        for phrase in self.hook_phrases:
            if phrase in text:
                scores['hook'] = 1.0
                break
        
        # 2. Check for emotional words
        emotion_count = sum(1 for word in self.emotional_words if word in text)
        scores['emotion'] = min(1.0, emotion_count * 0.2)  # Cap at 1.0
        
        # 3. Calculate pacing (words per second)
        word_count = len(text.split())
        duration = max(0.1, segment['end'] - segment['start'])  # Avoid division by zero
        words_per_second = word_count / duration
        
        # Ideal pacing is around 3-5 words per second
        if 3 <= words_per_second <= 5:
            scores['pacing'] = 1.0
        else:
            # Score drops off from ideal
            scores['pacing'] = 1.0 / (1.0 + abs(4 - words_per_second))  # 4 is ideal
        
        # 4. Score segment length (10-60 seconds is ideal)
        duration = segment['end'] - segment['start']
        if 10 <= duration <= 60:
            scores['length'] = 1.0
        elif duration < 10:
            scores['length'] = duration / 10.0  # Linearly scale up to 10s
        else:
            # Linearly scale down from 60s to 120s
            scores['length'] = max(0.0, 1.0 - (duration - 60) / 60.0)
        
        # 5. Get NLP intensity score
        if self.model is not None:
            try:
                # Encode the text and get a similarity score with some engaging phrases
                embeddings = self.model.encode([text] + ["This is very engaging content", "This is boring content"])
                # Compare with positive and negative examples
                similarity = np.dot(embeddings[0], embeddings[1:].T)
                # Normalize to 0-1 range
                scores['intensity'] = float((similarity[0] + 1) / 2)  # Convert from [-1, 1] to [0, 1]
            except Exception as e:
                logger.warning(f"Error calculating NLP intensity: {str(e)}")
        
        # Calculate weighted average of scores
        weights = {
            'hook': 0.3,
            'emotion': 0.2,
            'pacing': 0.2,
            'length': 0.2,
            'intensity': 0.1
        }
        
        total_score = sum(scores[category] * weight 
                         for category, weight in weights.items())
        
        return min(1.0, max(0.0, total_score))  # Ensure score is between 0 and 1
    
    @staticmethod
    def _format_duration(segments) -> str:
        """Format total duration from segments.
        
        Args:
            segments: List of transcript segments
            
        Returns:
            Formatted duration string (HH:MM:SS)
        """
        if not segments:
            return "00:00:00"
            
        # Get the end time of the last segment
        total_seconds = max(segment['end'] for segment in segments)
        
        # Convert to hours, minutes, seconds
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    async def analyze(
        self,
        transcript_path: Optional[str] = None,
        segments: Optional[List[Dict[str, Any]]] = None,
        min_clip_duration: float = 10.0,
        max_clip_duration: float = 60.0,
        top_k: int = 5,
        language: str = "en"
    ) -> Dict[str, Any]:
        """Analyze a transcript and return the most engaging clips.
        
        Either transcript_path or segments must be provided.
        
        Args:
            transcript_path: Path to the transcript JSON file (either this or segments must be provided)
            segments: List of transcript segments (either this or transcript_path must be provided)
            min_clip_duration: Minimum duration for a clip in seconds
            max_clip_duration: Maximum duration for a clip in seconds
            top_k: Maximum number of clips to return
            language: Language code for analysis
            
        Returns:
            Dictionary containing analysis results
            
        Raises:
            ValueError: If neither transcript_path nor segments is provided
            FileNotFoundError: If transcript file is not found
            json.JSONDecodeError: If transcript file is not valid JSON
            Exception: For other errors during analysis
        """
        logger.info(f"Starting analysis with params: transcript_path={transcript_path}, segments_provided={segments is not None}, language={language}")
        
        try:
            # Ensure model is loaded
            self.load_model()
            
            # Load transcript from file or use provided segments
            if transcript_path is not None:
                logger.info(f"Loading transcript from file: {transcript_path}")
                
                # Check if file exists and is readable
                if not os.path.exists(transcript_path):
                    error_msg = f"Transcript file not found: {transcript_path}"
                    logger.error(error_msg)
                    raise FileNotFoundError(error_msg)
                
                if not os.access(transcript_path, os.R_OK):
                    error_msg = f"No read permission for transcript file: {transcript_path}"
                    logger.error(error_msg)
                    raise PermissionError(error_msg)
                
                # Log file size
                file_size = os.path.getsize(transcript_path)
                logger.info(f"Transcript file size: {file_size} bytes")
                
                # Read and parse the file
                try:
                    with open(transcript_path, 'r', encoding='utf-8') as f:
                        transcript_data = json.load(f)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from {transcript_path}: {str(e)}")
                    # Try to read the first 1000 characters to help with debugging
                    try:
                        with open(transcript_path, 'r', encoding='utf-8') as f:
                            sample = f.read(1000)
                            logger.error(f"First 1000 chars of file: {sample}")
                    except Exception as read_err:
                        logger.error(f"Could not read file for debugging: {str(read_err)}")
                    raise
                
                logger.info(f"Successfully parsed transcript data. Type: {type(transcript_data)}")
                
                if isinstance(transcript_data, dict):
                    logger.info(f"Transcript data keys: {list(transcript_data.keys())}")
                    # Log first few values for debugging
                    for key, value in list(transcript_data.items())[:3]:
                        if isinstance(value, (str, int, float, bool)) or value is None:
                            logger.info(f"  {key}: {value}")
                        elif isinstance(value, (list, dict)):
                            logger.info(f"  {key}: {type(value)} with length {len(value)}")
                
                # Handle different transcript formats
                if isinstance(transcript_data, dict):
                    # Format: {"success": True, "transcript": [...], "language": "...", ...}
                    if 'transcript' in transcript_data:
                        transcript = transcript_data['transcript']
                        logger.info(f"Found 'transcript' key with {len(transcript) if transcript else 0} segments")
                        
                        # Extract additional metadata if available
                        if 'language' in transcript_data and transcript_data['language']:
                            language = transcript_data['language']
                            logger.info(f"Using language from transcript: {language}")
                        
                        if 'file_path' in transcript_data and transcript_data['file_path']:
                            video_name = os.path.basename(transcript_data['file_path'])
                            logger.info(f"Using video name from transcript: {video_name}")
                        else:
                            video_name = os.path.basename(transcript_path).replace('.json', '')
                            logger.info(f"Using default video name from filename: {video_name}")
                    else:
                        error_msg = "Transcript dictionary does not contain a 'transcript' key"
                        logger.error(error_msg)
                        logger.error(f"Available keys: {list(transcript_data.keys())}")
                        raise ValueError(error_msg)
                        
                elif isinstance(transcript_data, list):
                    # Format: [{"start": ..., "end": ..., "text": ...}, ...]
                    transcript = transcript_data
                    video_name = os.path.basename(transcript_path).replace('.json', '')
                    logger.info(f"Transcript is a list with {len(transcript)} segments")
                    logger.info(f"Using video name from filename: {video_name}")
                else:
                    error_msg = f"Unsupported transcript format: {type(transcript_data)}"
                    logger.error(error_msg)
                    raise ValueError("Unsupported transcript format. Expected a list of segments or dict with 'transcript' key.")
                
                # Log transcript summary
                logger.info(f"Successfully loaded transcript with {len(transcript) if transcript else 0} segments")
                if transcript and len(transcript) > 0:
                    first_seg = transcript[0]
                    logger.info(f"First segment type: {type(first_seg)}")
                    if isinstance(first_seg, dict):
                        logger.info(f"First segment keys: {list(first_seg.keys())}")
                        logger.info(f"First segment sample: {{start: {first_seg.get('start')}, end: {first_seg.get('end')}, text: {first_seg.get('text')[:50]}...}}")
                    else:
                        logger.warning(f"First segment is not a dictionary: {first_seg}")
                    
            elif segments is not None:
                logger.info(f"Using provided segments (count: {len(segments) if segments else 0})")
                transcript = segments
                video_name = "direct_upload"
                
                # Log first segment details
                if segments and len(segments) > 0:
                    first_seg = segments[0]
                    logger.info(f"First segment type: {type(first_seg)}")
                    if isinstance(first_seg, dict):
                        logger.info(f"First segment keys: {list(first_seg.keys())}")
                        logger.info(f"First segment sample: {{start: {first_seg.get('start')}, end: {first_seg.get('end')}, text: {first_seg.get('text')[:50]}...}}")
                    else:
                        logger.warning(f"First segment is not a dictionary: {first_seg}")
            else:
                error_msg = "Neither transcript_path nor segments provided"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # Validate segments with detailed logging
            logger.info("Starting transcript validation...")
            logger.info(f"Transcript type: {type(transcript)}")
            
            # Debug: Print the full transcript structure for inspection
            logger.info("Full transcript structure:")
            logger.info(json.dumps(transcript, indent=2, default=str)[:2000] + ("..." if len(json.dumps(transcript, default=str)) > 2000 else ""))
            
            # Check if transcript is a list or can be converted to one
            if not isinstance(transcript, (list, dict)):
                error_msg = f"Transcript is neither a list nor a dictionary. Type: {type(transcript)}"
                logger.error(error_msg)
                if hasattr(transcript, '__dict__'):
                    logger.error(f"Transcript object attributes: {vars(transcript)}")
                raise ValueError("Transcript must be a list of segments or a dictionary with a 'transcript' key")
                
            # If it's a dictionary, try to extract the transcript list
            if isinstance(transcript, dict):
                logger.info("Transcript is a dictionary, attempting to extract 'transcript' key")
                if 'transcript' in transcript and isinstance(transcript['transcript'], list):
                    logger.info("Found 'transcript' key with list value, using it")
                    transcript = transcript['transcript']
                else:
                    error_msg = "Transcript dictionary does not contain a 'transcript' key with list value"
                    logger.error(error_msg)
                    logger.error(f"Available keys: {list(transcript.keys())}")
                    raise ValueError(error_msg)
                    
            if not isinstance(transcript, list):
                error_msg = f"Failed to convert transcript to a list. Final type: {type(transcript)}"
                logger.error(error_msg)
                raise ValueError("Could not convert transcript to a list of segments")
                
            logger.info(f"Validating {len(transcript)} segments...")
            
            for i, segment in enumerate(transcript):
                try:
                    logger.info(f"Processing segment {i}: {str(segment)[:200]}...")
                    
                    if not isinstance(segment, dict):
                        logger.error(f"Segment at index {i} is not a dictionary. Type: {type(segment)}")
                        if hasattr(segment, '__dict__'):
                            logger.error(f"Segment object attributes: {vars(segment)}")
                        raise ValueError(
                            f"Segment at index {i} is not a dictionary. "
                            "Each segment must be a dictionary with 'start', 'end', and 'text' keys."
                        )
                    
                    # Log segment keys for debugging
                    segment_keys = list(segment.keys())
                    logger.info(f"Segment {i} keys: {segment_keys}")
                    
                    # Check for required keys
                    required_keys = ['start', 'end', 'text']
                    missing_keys = [key for key in required_keys if key not in segment]
                    if missing_keys:
                        logger.error(f"Segment at index {i} is missing required keys: {missing_keys}")
                        logger.error(f"Available keys: {segment_keys}")
                        logger.error(f"Segment content: {segment}")
                        raise ValueError(
                            f"Segment at index {i} is missing required fields: {', '.join(missing_keys)}. "
                            "Each segment must have 'start', 'end', and 'text' keys."
                        )
                    
                    # Log values for debugging
                    for key in required_keys:
                        if key in segment:
                            logger.info(f"Segment {i} {key}: {segment[key]} (type: {type(segment[key])})")
                    
                    # Validate types
                    if not isinstance(segment['start'], (int, float)):
                        logger.error(f"Segment at index {i} has invalid start time. Type: {type(segment['start'])}, Value: {segment['start']}")
                        raise ValueError(
                            f"Segment at index {i} has invalid start time. "
                            "'start' must be a number."
                        )
                        
                    if not isinstance(segment['end'], (int, float)):
                        logger.error(f"Segment at index {i} has invalid end time. Type: {type(segment['end'])}, Value: {segment['end']}")
                        raise ValueError(
                            f"Segment at index {i} has invalid end time. "
                            "'end' must be a number."
                        )
                        
                    if not isinstance(segment['text'], str):
                        logger.error(f"Segment at index {i} has invalid text. Type: {type(segment['text'])}, Value: {segment['text']}")
                        raise ValueError(f"Segment at index {i} has invalid text. 'text' must be a string.")
                    
                    # Log first segment details for debugging
                    if i == 0 or i == len(transcript) - 1:
                        logger.info(f"Segment {i} sample: {segment}")
                        
                except Exception as e:
                    logger.error(f"Error validating segment {i}: {str(e)}")
                    logger.error(f"Segment content: {segment}")
                    raise
            
            # Score each segment
            scored_segments = []
            for segment in transcript:
                score = self._score_segment(segment)
                scored_segments.append({
                    **segment,
                    'score': score,
                    'duration': segment['end'] - segment['start']
                })
            
            # Sort by score and get top clips
            scored_segments.sort(key=lambda x: x['score'], reverse=True)
            
            # Select non-overlapping top clips
            selected_clips = self._select_non_overlapping_clips(
                scored_segments,
                min_duration=min_clip_duration,
                max_duration=max_clip_duration,
                top_k=top_k
            )
            
            # Prepare output
            output = {
                'video': video_name,
                'language': language,
                'total_duration': self._format_duration(transcript),
                'analyzed_at': datetime.utcnow().isoformat(),
                'recommended_clips': selected_clips[:top_k]
            }
            
            return output
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in transcript file: {str(e)}")
            raise ValueError(f"Invalid transcript file: {str(e)}")
        except FileNotFoundError as e:
            logger.error(f"Transcript file not found: {transcript_path}")
            raise FileNotFoundError(f"Transcript file not found: {transcript_path}" if transcript_path else "No transcript provided")
        except Exception as e:
            logger.error(f"Error analyzing transcript: {str(e)}", exc_info=True)
            raise
    
    def _select_non_overlapping_clips(
        self, 
        scored_segments: List[Dict[str, Any]],
        min_duration: float = 10.0,
        max_duration: float = 60.0,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Select non-overlapping clips from scored segments.
        
        Args:
            scored_segments: List of scored segments
            min_duration: Minimum clip duration in seconds
            max_duration: Maximum clip duration in seconds
            top_k: Maximum number of clips to return
            
        Returns:
            List of selected clips with metadata
        """
        selected = []
        used_timestamps = []
        
        for segment in scored_segments:
            # Skip segments that are too short or too long
            if segment['duration'] < min_duration or segment['duration'] > max_duration:
                continue
                
            # Check for overlap with already selected clips
            overlap = False
            for used_start, used_end in used_timestamps:
                if (segment['start'] <= used_end and segment['end'] >= used_start):
                    overlap = True
                    break
            
            if not overlap:
                selected.append({
                    'start': round(segment['start'], 2),
                    'end': round(segment['end'], 2),
                    'text': segment['text'],
                    'score': round(segment['score'], 2),
                    'reason': self._generate_reason(segment)
                })
                used_timestamps.append((segment['start'], segment['end']))
                
                # Stop if we have enough clips
                if len(selected) >= top_k:
                    break
        
        return selected
    
    def _generate_reason(self, segment: Dict[str, Any]) -> str:
        """Generate a human-readable reason for why a clip was selected."""
        reasons = []
        
        # Check for hook phrases
        text_lower = segment['text'].lower()
        if any(hook in text_lower for hook in self.hook_phrases):
            reasons.append("contains engaging hook phrase")
            
        # Check for emotional words
        emotion_count = sum(1 for word in self.emotional_words if word in text_lower)
        if emotion_count >= 2:  # At least 2 emotional words
            reasons.append("high emotional content")
            
        # Check pacing (words per second)
        word_count = len(segment['text'].split())
        duration = max(0.1, segment['end'] - segment['start'])
        words_per_second = word_count / duration
        
        if words_per_second > 4:  # Fast-paced
            reasons.append("fast-paced delivery")
        elif words_per_second < 2:  # Slow-paced
            reasons.append("dramatic pacing")
            
        # Check duration
        if duration > 45:  # Longer segments
            reasons.append("detailed explanation")
        elif duration < 20:  # Shorter segments
            reasons.append("concise delivery")
        
        return ", ".join(reasons) if reasons else "high engagement potential"
