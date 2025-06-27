import os
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.services.analyzer_service import AnalyzerService

# Sample transcript data for testing
SAMPLE_TRANSCRIPT = [
    {"start": 0.0, "end": 5.0, "text": "Welcome to our channel!"},
    {"start": 5.0, "end": 15.0, "text": "Today we're doing something crazy and you won't believe what happens next!"},
    {"start": 15.0, "end": 25.0, "text": "We're going to test some amazing new technology that will blow your mind."},
    {"start": 25.0, "end": 35.0, "text": "This is just some normal talking that's not very exciting."},
    {"start": 35.0, "end": 50.0, "text": "But wait until you see this incredible result! It's absolutely mind-blowing!"},
    {"start": 50.0, "end": 60.0, "text": "Thanks for watching, don't forget to like and subscribe!"}
]

# Create a fixture for the analyzer
@pytest.fixture
def analyzer():
    # Patch the model loading to avoid downloading during tests
    with patch('sentence_transformers.SentenceTransformer'):
        analyzer = AnalyzerService()
        analyzer.model = MagicMock()
        # Mock the encode method to return dummy embeddings
        analyzer.model.encode.return_value = [[0.1] * 384]  # All-MiniLM-L6-v2 has 384 dimensions
        yield analyzer

# Create a temporary transcript file for testing
@pytest.fixture
def temp_transcript_file(tmp_path):
    transcript_file = tmp_path / "test_transcript.json"
    with open(transcript_file, 'w', encoding='utf-8') as f:
        json.dump(SAMPLE_TRANSCRIPT, f)
    return str(transcript_file)

def test_analyzer_initialization(analyzer):
    """Test that the analyzer initializes correctly."""
    assert analyzer is not None
    assert analyzer.model is not None

def test_score_segment_with_hook_phrase(analyzer):
    """Test scoring a segment with a hook phrase."""
    segment = {"start": 0, "end": 10, "text": "You won't believe what happens next!"}
    score = analyzer._score_segment(segment)
    assert 0 <= score <= 1.0
    # Should have a higher score due to hook phrase
    assert score > 0.5

def test_score_segment_with_emotional_words(analyzer):
    """Test scoring a segment with emotional words."""
    segment = {"start": 0, "end": 10, "text": "This is absolutely amazing and incredible!"}
    score = analyzer._score_segment(segment)
    assert 0 <= score <= 1.0
    # Should have a higher score due to emotional words
    assert score > 0.3

def test_analyze_transcript(analyzer, temp_transcript_file):
    """Test analyzing a complete transcript file."""
    result = analyzer.analyze(temp_transcript_file)
    
    assert 'recommended_clips' in result
    assert isinstance(result['recommended_clips'], list)
    assert len(result['recommended_clips']) > 0
    
    # Check clip structure
    clip = result['recommended_clips'][0]
    assert 'start' in clip
    assert 'end' in clip
    assert 'text' in clip
    assert 'score' in clip
    assert 'reason' in clip

def test_select_non_overlapping_clips(analyzer):
    """Test selecting non-overlapping clips."""
    # Create test segments with some overlap
    segments = [
        {"start": 0, "end": 10, "text": "First segment", "score": 0.9, "duration": 10},
        {"start": 5, "end": 15, "text": "Overlapping segment", "score": 0.8, "duration": 10},
        {"start": 20, "end": 30, "text": "Non-overlapping segment", "score": 0.7, "duration": 10},
    ]
    
    selected = analyzer._select_non_overlapping_clips(segments)
    
    # Should select the highest scoring non-overlapping segments
    assert len(selected) == 2  # First and third segments
    assert selected[0]['text'] == "First segment"
    assert selected[1]['text'] == "Non-overlapping segment"

def test_analyze_endpoint(client, temp_transcript_file):
    """Test the /analyze endpoint."""
    # Copy the test transcript to the expected location
    os.makedirs("/data/transcripts", exist_ok=True)
    import shutil
    shutil.copy(temp_transcript_file, "/data/transcripts/test_video_transcript.json")
    
    response = client.post(
        "/api/v1/analyze",
        json={"filename": "test_video_transcript.json"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "recommended_clips" in data
    assert isinstance(data["recommended_clips"], list)
