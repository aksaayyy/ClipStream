#!/usr/bin/env python3
"""
Test script for the ClipStream Transcriber Service.

This script provides utilities to test the transcriber service locally,
both with and without Docker.
"""

import os
import sys
import json
import logging
import argparse
import requests
from pathlib import Path
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("transcriber-test")

# Default configuration
DEFAULT_HOST = "http://localhost"
DEFAULT_PORT = 5002
DEFAULT_API_BASE = f"{DEFAULT_HOST}:{DEFAULT_PORT}"

class TranscriberTester:
    """Test client for the Transcriber Service."""
    
    def __init__(self, base_url: str = DEFAULT_API_BASE):
        """Initialize the test client."""
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api/v1"
        
    def check_health(self) -> bool:
        """Check if the service is healthy."""
        try:
            response = requests.get(f"{self.base_url}/health")
            response.raise_for_status()
            data = response.json()
            logger.info(f"Service health: {data}")
            return data.get("status") == "healthy"
        except requests.RequestException as e:
            logger.error(f"Health check failed: {str(e)}")
            return False
    
    def transcribe_file(self, filename: str, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Send a transcription request for a file.
        
        Args:
            filename: Name of the file in the downloads directory
            language: Optional language code (e.g., 'en', 'es')
            
        Returns:
            Dictionary containing the transcription result
        """
        url = f"{self.api_url}/transcribe"
        payload = {"filename": filename}
        if language:
            payload["language"] = language
            
        try:
            logger.info(f"Sending transcription request for {filename}")
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Transcription request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return {"success": False, "error": str(e)}

def run_tests(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
    """Run a series of tests against the transcriber service."""
    base_url = f"{host}:{port}"
    tester = TranscriberTester(base_url)
    
    logger.info(f"Testing transcriber service at {base_url}")
    
    # Test 1: Health check
    logger.info("\n=== Running Health Check ===")
    if not tester.check_health():
        logger.error("Health check failed. Is the service running?")
        return False
    
    # Test 2: Get service info
    try:
        logger.info("\n=== Getting Service Info ===")
        response = requests.get(f"{base_url}")
        response.raise_for_status()
        logger.info(f"Service info: {json.dumps(response.json(), indent=2)}")
    except requests.RequestException as e:
        logger.error(f"Failed to get service info: {str(e)}")
    
    # Test 3: List available test files
    test_files_dir = os.path.join(os.path.dirname(__file__), "test_data")
    if os.path.exists(test_files_dir):
        logger.info("\n=== Available Test Files ===")
        for f in os.listdir(test_files_dir):
            if f.endswith(('.mp3', '.wav', '.mp4')):
                logger.info(f"- {f}")
    
    return True

def main():
    """Main entry point for the test script."""
    parser = argparse.ArgumentParser(description="Test the ClipStream Transcriber Service")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Service host (default: localhost)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Service port (default: 5002)")
    parser.add_argument("--transcribe", help="Transcribe a specific file")
    parser.add_argument("--language", help="Language code for transcription (e.g., 'en', 'es')")
    
    args = parser.parse_args()
    
    if args.transcribe:
        # Transcribe a specific file
        tester = TranscriberTester(f"{args.host}:{args.port}")
        result = tester.transcribe_file(args.transcribe, args.language)
        print(json.dumps(result, indent=2))
    else:
        # Run all tests
        run_tests(args.host, args.port)

if __name__ == "__main__":
    main()
