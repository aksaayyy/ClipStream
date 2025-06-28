import sys
import json
from pathlib import Path

# Add the analyzer service to the Python path
sys.path.append('/app')

# Import the analyzer service
from app.services.analyzer_service import AnalyzerService

async def test_analyzer(transcript_path):
    print(f"Testing analyzer with transcript: {transcript_path}")
    
    # Initialize the analyzer
    analyzer = AnalyzerService()
    
    try:
        # Test the analyze method directly
        result = await analyzer.analyze(
            transcript_path=transcript_path,
            min_clip_duration=10.0,
            max_clip_duration=60.0,
            top_k=3,
            language="pa"
        )
        
        print("Analysis successful!")
        print(f"Result: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return True
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print("Traceback:")
        print(traceback.format_exc())
        return False

if __name__ == "__main__":
    import asyncio
    
    if len(sys.argv) > 1:
        transcript_path = sys.argv[1]
        asyncio.run(test_analyzer(transcript_path))
    else:
        print("Please provide a transcript file path")
