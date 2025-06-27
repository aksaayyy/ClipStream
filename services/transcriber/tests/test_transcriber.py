import os
import sys
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

client = TestClient(app)

def test_health_check():
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert "transcriber" in response.json()["service"]

# Note: This is a placeholder test for the transcribe endpoint
# We'll expand this with actual file handling tests once the basic service is working
# @pytest.mark.skip(reason="Requires actual file handling implementation")
# def test_transcribe_endpoint():
#     """Test the transcribe endpoint with a sample file"""
#     # This test requires a sample audio file to be present in the test data directory
#     test_file = "test_audio.mp3"
#     
#     response = client.post(
#         "/transcribe",
#         json={"filename": test_file}
#     )
#     
#     assert response.status_code == 200
#     data = response.json()
#     assert data["success"] is True
#     assert "transcript" in data
#     assert isinstance(data["transcript"], list)
#     if len(data["transcript"]) > 0:
#         assert "start" in data["transcript"][0]
#         assert "end" in data["transcript"][0]
#         assert "text" in data["transcript"][0]

def test_invalid_file():
    """Test the transcribe endpoint with a non-existent file"""
    response = client.post(
        "/transcribe",
        json={"filename": "nonexistent_file.mp4"}
    )
    
    # This will fail once we implement actual file checking
    # For now, it's expected to return 200 with success=False
    assert response.status_code == 200
    assert response.json()["success"] is False
