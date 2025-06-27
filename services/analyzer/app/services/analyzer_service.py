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
        try:
            # Ensure model is loaded
            self.load_model()
            
            # Load transcript from file or use provided segments
            if transcript_path is not None:
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    transcript = json.load(f)
                video_name = os.path.basename(transcript_path).replace('_transcript.json', '')
            elif segments is not None:
                transcript = segments
                video_name = "direct_upload"
            else:
                raise ValueError("Either transcript_path or segments must be provided")
            
            if not isinstance(transcript, list):
                raise ValueError("Invalid transcript format. Expected a list of segments.")
            
            # Validate segments
            for i, segment in enumerate(transcript):
                if not all(key in segment for key in ['start', 'end', 'text']):
                    raise ValueError(
                        f"Segment at index {i} is missing required fields. "
                        "Each segment must have 'start', 'end', and 'text' keys."
                    )
                if not isinstance(segment['start'], (int, float)) or not isinstance(segment['end'], (int, float)):
                    raise ValueError(
                        f"Segment at index {i} has invalid timestamp values. "
                        "'start' and 'end' must be numbers."
                    )
                if not isinstance(segment['text'], str):
                    raise ValueError(f"Segment at index {i} has invalid text. 'text' must be a string.")
            
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
