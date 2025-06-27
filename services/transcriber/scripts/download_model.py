#!/usr/bin/env python3
"""
Script to download the Whisper model manually.
"""
import os
import whisper
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("model-downloader")

def download_model(model_name: str = "base"):
    """Download the specified Whisper model.
    
    Args:
        model_name: Name of the Whisper model to download (tiny, base, small, medium, large)
    """
    try:
        logger.info(f"Downloading Whisper {model_name} model...")
        
        # This will download the model to the default cache directory
        model = whisper.load_model(model_name)
        
        # Get the cache directory
        cache_dir = os.path.join(Path.home(), ".cache", "whisper")
        logger.info(f"Model downloaded to: {cache_dir}")
        
        # List downloaded files
        if os.path.exists(cache_dir):
            logger.info("Downloaded model files:")
            for root, _, files in os.walk(cache_dir):
                for file in files:
                    if file.endswith(".pt"):  # Show PyTorch model files
                        file_path = os.path.join(root, file)
                        file_size = os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
                        logger.info(f"- {file} ({file_size:.2f} MB)")
        
        return True
    except Exception as e:
        logger.error(f"Failed to download model: {str(e)}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Download Whisper model")
    parser.add_argument("--model", type=str, default="base",
                       help="Whisper model to download (tiny, base, small, medium, large)")
    
    args = parser.parse_args()
    
    print(f"Downloading Whisper {args.model} model...")
    if download_model(args.model):
        print("\nModel downloaded successfully!")
        print("\nTo use this model, set the WHISPER_MODEL environment variable to the model name.")
        print("Example:")
        print(f"  export WHISPER_MODEL={args.model}")
    else:
        print("\nFailed to download the model. Check the logs for details.")
