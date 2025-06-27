"""Test script for the analyzer service API."""
import json
import requests
from typing import List, Dict, Any

def test_analyze_endpoint():
    """Test the analyze endpoint with a sample transcript."""
    url = "http://localhost:5003/api/v1/analyze"
    
    # Sample transcript data
    segments = [
        {
            "text": "This is a test sentence about artificial intelligence and machine learning.",
            "start": 0.0,
            "end": 5.0
        },
        {
            "text": "AI is transforming industries across the globe.",
            "start": 5.0,
            "end": 9.0
        },
        {
            "text": "Machine learning models can analyze vast amounts of data.",
            "start": 9.0,
            "end": 14.0
        }
    ]
    
    # Prepare the request payload according to the API spec
    payload = {
        "segments": segments,
        "min_clip_duration": 5.0,
        "max_clip_duration": 30.0,
        "top_k": 3,
        "language": "en"
    }
    
    # Set headers
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        print("Sending request to:", url)
        print("Request payload:", json.dumps(payload, indent=2))
        
        # Make the request
        response = requests.post(
            url,
            json=payload,  # Use json parameter to automatically serialize to JSON
            headers=headers,
            timeout=120  # 120 seconds timeout
        )
        
        # Print the response
        print(f"\nStatus Code: {response.status_code}")
        print("Response:")
        
        try:
            print(json.dumps(response.json(), indent=2))
        except ValueError:
            print(response.text)
        
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print("Response content:", e.response.text)
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("Testing analyze endpoint...")
    success = test_analyze_endpoint()
    print(f"Test {'passed' if success else 'failed'}")
