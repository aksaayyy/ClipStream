"""
Core analyzer logic for identifying engaging video clips.
"""
import random
from typing import List, Dict, Any, Tuple, Optional
from ..models import TranscriptSegment, ClipSuggestion

class ClipAnalyzer:
    """Analyzes transcripts to identify engaging video clips."""
    
    def __init__(self):
        # Phrases that indicate engaging content
        self.hook_phrases = [
            "you won't believe", "this is why", "what happened next", "watch what happens",
            "I was shocked when", "wait till you see", "here's the thing", "the truth about",
            "they didn't expect this", "what happened was", "here's how", "the secret to",
            "this is what happens when", "I couldn't believe my eyes", "you need to see this"
        ]
        
        # Emotional and engaging words
        self.emotional_words = [
            "amazing", "unbelievable", "incredible", "shocking", "mind-blowing",
            "hilarious", "crazy", "insane", "epic", "legendary", "emotional",
            "heartbreaking", "tears", "crying", "laughing", "dying", "unreal",
            "astonishing", "stunning", "breathtaking", "jaw-dropping", "phenomenal"
        ]
        
        # Words that indicate questions or curiosity
        self.question_words = ["why", "how", "what", "when", "where", "who", "which"]
        
        # Words that indicate transitions or conclusions
        self.transition_words = ["but", "however", "therefore", "thus", "so", "because"]
    
    def analyze_transcript(
        self, 
        transcript: List[Dict[str, Any]],
        min_duration: float = 10.0,
        max_duration: float = 60.0,
        top_k: int = 3,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Analyze a transcript and return the most engaging clips.
        
        Args:
            transcript: List of transcript segments
            min_duration: Minimum clip duration in seconds
            max_duration: Maximum clip duration in seconds
            top_k: Number of top clips to return
            language: Language code for analysis
            
        Returns:
            Dict containing analysis results
        """
        if not isinstance(transcript, list):
            return {"error": "Invalid transcript format. Expected a list of segments."}
        
        # Convert to TranscriptSegment objects if needed
        segments = []
        for seg in transcript:
            if isinstance(seg, dict):
                segments.append(TranscriptSegment(**seg))
            elif isinstance(seg, TranscriptSegment):
                segments.append(seg)
        
        # Score each segment
        scored_segments = []
        for segment in segments:
            score = self._score_segment(segment)
            scored_segments.append({
                'start': segment.start,
                'end': segment.end,
                'text': segment.text,
                'score': round(score, 2),
                'duration': round(segment.end - segment.start, 2)
            })
        
        # Sort by score and get top clips
        scored_segments.sort(key=lambda x: x['score'], reverse=True)
        
        # Select non-overlapping top clips
        selected_clips = self._select_non_overlapping_clips(
            scored_segments, 
            min_duration=min_duration,
            max_duration=max_duration,
            max_clips=top_k
        )
        
        # Calculate total duration
        total_duration = self._calculate_total_duration(segments)
        
        # Convert to ClipSuggestion objects
        clip_suggestions = []
        for clip in selected_clips:
            clip_suggestions.append(ClipSuggestion(
                start=clip['start'],
                end=clip['end'],
                text=clip['text'],
                score=clip['score'],
                reason=clip['reason']
            ))
        
        return {
            'success': True,
            'recommended_clips': clip_suggestions,
            'total_duration': total_duration
        }
    
    def _score_segment(self, segment: TranscriptSegment) -> float:
        """Score a single transcript segment."""
        text = segment.text.lower()
        score = 0.0
        
        # Check for hook phrases (highest weight)
        for phrase in self.hook_phrases:
            if phrase in text:
                score += 0.4  # Higher weight for hooks
                break
        
        # Check for emotional words
        emotion_count = sum(1 for word in self.emotional_words if word in text)
        score += min(0.3, emotion_count * 0.1)  # Cap emotional score at 0.3
        
        # Check for questions (indicates engagement)
        if any(text.strip().startswith(word) for word in self.question_words):
            score += 0.15
        
        # Check for transitions (often indicate important points)
        if any(f" {word} " in f" {text} " for word in self.transition_words):
            score += 0.1
        
        # Score based on length (10-30 seconds is ideal)
        duration = segment.end - segment.start
        if 10 <= duration <= 30:
            score += 0.2
        elif duration < 10:
            score += (duration / 10.0) * 0.2
        else:
            score += max(0, 0.2 - (duration - 30) * 0.01)
        
        # Add some randomness to differentiate segments
        score = min(1.0, score + random.uniform(0, 0.05))
        
        return score
    
    def _select_non_overlapping_clips(
        self, 
        segments: List[Dict[str, Any]], 
        min_duration: float = 5.0,
        max_duration: float = 60.0,
        max_clips: int = 5,
        min_gap: float = 5.0
    ) -> List[Dict[str, Any]]:
        """
        Select non-overlapping clips from scored segments.
        
        Args:
            segments: List of scored segments
            min_duration: Minimum clip duration in seconds
            max_duration: Maximum clip duration in seconds
            max_clips: Maximum number of clips to return
            min_gap: Minimum gap between clips in seconds
            
        Returns:
            List of selected clips with metadata
        """
        selected = []
        used_timestamps = []
        
        for segment in segments:
            # Skip segments that are too short or too long
            if not (min_duration <= segment['duration'] <= max_duration):
                continue
                
            # Check for overlap with already selected clips
            overlap = False
            for used_start, used_end in used_timestamps:
                if (segment['start'] <= (used_end + min_gap) and 
                    segment['end'] >= (used_start - min_gap)):
                    overlap = True
                    break
            
            if not overlap:
                selected.append({
                    'start': round(segment['start'], 1),
                    'end': round(segment['end'], 1),
                    'text': segment['text'],
                    'score': segment['score'],
                    'reason': self._generate_reason(segment),
                    'duration': segment['duration']
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
        
        # Check for hook phrases
        if any(hook in text for hook in self.hook_phrases):
            reasons.append("engaging hook phrase")
            
        # Check for emotional content
        emotion_count = sum(1 for word in self.emotional_words if word in text)
        if emotion_count >= 2:
            reasons.append("emotional content")
        elif emotion_count == 1:
            reasons.append("emotional word")
            
        # Check for questions
        if any(text.strip().startswith(word) for word in self.question_words):
            reasons.append("question format")
            
        # Check duration
        duration = segment['duration']
        if duration > 25:
            reasons.append("detailed explanation")
        elif duration < 10:
            reasons.append("concise delivery")
            
        # If no specific reasons, use a generic one based on score
        if not reasons:
            if segment['score'] > 0.7:
                reasons.append("high engagement potential")
            elif segment['score'] > 0.4:
                reasons.append("moderate engagement potential")
            else:
                reasons.append("potentially interesting content")
        
        # Join reasons with commas, and use 'and' for the last one if multiple
        if len(reasons) > 1:
            return ", ".join(reasons[:-1]) + ", and " + reasons[-1]
        return reasons[0] if reasons else "selected content"
    
    def _calculate_total_duration(self, segments: List[TranscriptSegment]) -> str:
        """Calculate and format total duration from transcript."""
        if not segments:
            return "00:00:00"
            
        total_seconds = max(segment.end for segment in segments)
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
