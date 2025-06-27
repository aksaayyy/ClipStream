import requests
import os
import time
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("yt-fetcher-test")

def test_health_check():
    """Test the health check endpoint"""
    try:
        response = requests.get("http://localhost:8000/health")
        logger.info(f"Health check status: {response.status_code}")
        logger.info(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return False

def test_download_video():
    """Test downloading a video"""
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
    
    try:
        logger.info(f"Testing download with URL: {test_url}")
        response = requests.post(
            "http://localhost:8000/fetch",
            json={"url": test_url}
        )
        
        logger.info(f"Status code: {response.status_code}")
        logger.info(f"Response: {response.json()}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                file_path = result.get('path')
                if file_path and os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    logger.info(f"File downloaded successfully: {file_path} ({file_size} bytes)")
                    return True
        return False
    except Exception as e:
        logger.error(f"Download test failed: {str(e)}")
        return False

def main():
    # Start the service (in a real scenario, you'd do this in a separate terminal)
    logger.info("Starting tests...")
    
    # Test 1: Health check
    logger.info("\n=== Testing Health Check ===")
    health_ok = test_health_check()
    logger.info(f"Health check {'PASSED' if health_ok else 'FAILED'}")
    
    if not health_ok:
        logger.error("Health check failed. Is the service running?")
        logger.info("To start the service, run: uvicorn services.yt-fetcher.app.main:app --reload")
        return
    
    # Test 2: Video download
    logger.info("\n=== Testing Video Download ===")
    download_ok = test_download_video()
    logger.info(f"Download test {'PASSED' if download_ok else 'FAILED'}")
    
    # Summary
    logger.info("\n=== Test Summary ===")
    logger.info(f"Health Check: {'PASSED' if health_ok else 'FAILED'}")
    logger.info(f"Video Download: {'PASSED' if download_ok else 'FAILED'}")

if __name__ == "__main__":
    main()
