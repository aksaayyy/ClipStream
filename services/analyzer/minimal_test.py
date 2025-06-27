#!/usr/bin/env python3
"""
Minimal test script for Clip Analyzer service.
This version doesn't require heavy dependencies.
"""
import json
import os
from pathlib import Path

class MinimalAnalyzer:
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
    
    def analyze_transcript(self, transcript):
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
        
        return {
            'success': True,
            'recommended_clips': selected_clips[:3]  # Return top 3 clips
        }
    
    def _score_segment(self, segment):
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
        import random
        score = min(1.0, score + random.uniform(0, 0.1))
        
        return score
    
    def _select_non_overlapping_clips(self, segments):
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
                if len(selected) >= 5:
                    break
        
        return selected
    
    def _generate_reason(self, segment):
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

def main():
    # Sample transcript for testing
    sample_transcript = [
        {"start": 0.0, "end": 5.0, "text": "Welcome to our channel!"},
        {"start": 5.0, "end": 15.0, "text": "Today we're doing something crazy and you won't believe what happens next!"},
        {"start": 15.0, "end": 25.0, "text": "We're going to test some amazing new technology that will blow your mind."},
        {"start": 25.0, "end": 35.0, "text": "This is just some normal talking that's not very exciting."},
        {"start": 35.0, "end": 50.0, "text": "But wait until you see this incredible result! It's absolutely mind-blowing!"},
        {"start": 50.0, "end": 60.0, "text": "Thanks for watching, don't forget to like and subscribe!"}
    ]
    
    # Initialize and run the analyzer
    analyzer = MinimalAnalyzer()
    result = analyzer.analyze_transcript(sample_transcript)
    
    # Print results
    print("\n=== Clip Analysis Results ===\n")
    if 'error' in result:
        print(f"Error: {result['error']}")
        return
    
    print(f"Found {len(result['recommended_clips'])} recommended clips:\n")
    
    for i, clip in enumerate(result['recommended_clips'], 1):
        print(f"Clip {i} (Score: {clip['score']:.2f}):")
        print(f"  Time: {clip['start']:.1f}s - {clip['end']:.1f}s")
        print(f"  Reason: {clip['reason']}")
        print(f"  Text: \"{clip['text']}\"\n")

if __name__ == "__main__":
    main()
