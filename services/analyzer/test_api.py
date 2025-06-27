#!/usr/bin/env python3
"""
Test script for the Clip Analyzer API.

This script tests the main functionality of the Clip Analyzer API
by making HTTP requests to the running service.
"""
import os
import sys
import json
import time
import requests
from typing import Dict, Any, List
from pprint import pprint

# Configuration
BASE_URL = "http://localhost:5003"
TEST_VIDEO_ID = "test_video_123"

def print_test_header(test_name: str) -> None:
    """Print a formatted test header."""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}".center(80))
    print("="*80)

def test_health_check() -> bool:
    """Test the health check endpoint."""
    print_test_header("Health Check")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status Code: {response.status_code}")
        print("Response:")
        pprint(response.json())
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_analyze_endpoint() -> bool:
    """Test the analyze endpoint with a sample transcript."""
    print_test_header("Analyze Endpoint")
    
    # Sample transcript data
    transcript_segments = [
        {"start": 0.0, "end": 5.0, "text": "Welcome to our channel!"},
        {"start": 5.0, "end": 15.0, "text": "Today we're doing something crazy and you won't believe what happens next!"},
        {"start": 15.0, "end": 25.0, "text": "We're going to test some amazing new technology that will blow your mind."},
        {"start": 25.0, "end": 35.0, "text": "This is just some normal talking that's not very exciting."},
        {"start": 35.0, "end": 50.0, "text": "But wait until you see this incredible result! It's absolutely mind-blowing!"},
        {"start": 50.0, "end": 60.0, "text": "Thanks for watching, don't forget to like and subscribe!"}
    ]
    
    analyze_request = {
        "segments": transcript_segments,
        "min_clip_duration": 5.0,
        "max_clip_duration": 60.0,
        "top_k": 3,
        "language": "en"
    }
    
    try:
        # Print test information
        print("Sample transcript data prepared")
        print(f"Transcript length: {len(transcript_segments)} segments")
        
        # Test the analyze endpoint with direct segments
        print("\nSending analyze request with direct segments...")
        print(f"Request payload: {json.dumps(analyze_request, indent=2)}")
        
        # Increase timeout to 5 minutes (300 seconds) to allow for model loading
        print("This may take a few minutes for the first request as the model loads...")
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/analyze",
                json=analyze_request,
                timeout=300  # 5 minutes timeout for first request
            )
            elapsed = time.time() - start_time
            print(f"Request completed in {elapsed:.2f} seconds")
        except requests.exceptions.Timeout:
            print("Request timed out after 5 minutes")
            raise
        except Exception as e:
            print(f"Request failed with error: {str(e)}")
            raise
        
        print(f"Status Code: {response.status_code}")
        print("Response:")
        pprint(response.json())
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success") and "recommended_clips" in result:
                print(f"\nFound {len(result['recommended_clips'])} recommended clips!")
                for i, clip in enumerate(result["recommended_clips"], 1):
                    print(f"\nClip {i} (Score: {clip['score']:.2f}):")
                    print(f"  Start: {clip['start']:.1f}s, End: {clip['end']:.1f}s")
                    print(f"  Text: {clip['text']}")
                    print(f"  Reason: {clip['reason']}")
        
        return response.status_code == 200
        
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_tests() -> None:
    """Run all tests and print summary."""
    print("="*80)
    print("CLIP ANALYZER API TEST SUITE".center(80))
    print("="*80)
    
    tests = [
        ("Health Check", test_health_check),
        ("Analyze Endpoint", test_analyze_endpoint),
    ]
    
    results = []
    
    for name, test_func in tests:
        print(f"\nStarting test: {name}")
        start_time = time.time()
        success = test_func()
        duration = time.time() - start_time
        status = "PASSED" if success else "FAILED"
        results.append((name, status, f"{duration:.2f}s"))
        print(f"\n{name}: {status} ({duration:.2f} seconds)")
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY".center(80))
    print("="*80)
    
    for name, status, duration in results:
        print(f"{name:<30} {status:>10} {duration:>10}")
    
    # Print overall status
    all_passed = all(status == "PASSED" for _, status, _ in results)
    print("\n" + "="*80)
    if all_passed:
        print("ALL TESTS PASSED!".center(80))
    else:
        print("SOME TESTS FAILED".center(80))
    print("="*80)

if __name__ == "__main__":
    run_tests()
