#!/usr/bin/env python3
"""
Simple test script to verify yt-dlp functionality.
"""
import yt_dlp
import json
import sys

def test_ytdlp(url):
    """Test yt-dlp with the given URL."""
    ydl_opts = {
        'format': 'best[height<=1080]',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': False,
        'extract_flat': False,
        'forcejson': True,
        'nocheckcertificate': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Testing URL: {url}")
            info = ydl.extract_info(url, download=False)
            print("\nSuccess! Video info:")
            print(f"Title: {info.get('title')}")
            print(f"Duration: {info.get('duration')} seconds")
            print(f"Formats: {len(info.get('formats', []))} available")
            return True
    except Exception as e:
        print(f"\nError: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_url = sys.argv[1]
    else:
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    print(f"yt-dlp test script (Python module version: {yt_dlp.version.__version__})")
    print("-" * 50)
    success = test_ytdlp(test_url)
    print("-" * 50)
    print("Test", "PASSED" if success else "FAILED")
