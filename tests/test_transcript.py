import json
import os

def test_transcript(filepath):
    try:
        print(f"Testing transcript file: {filepath}")
        
        # Check if file exists
        if not os.path.exists(filepath):
            print(f"Error: File not found: {filepath}")
            return False
            
        print(f"File exists. Size: {os.path.getsize(filepath)} bytes")
        
        # Try to load the file
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        print("JSON loaded successfully")
        print(f"Data type: {type(data)}")
        
        # Check the structure
        if isinstance(data, dict):
            print("Top level is a dictionary")
            print(f"Keys: {list(data.keys())}")
            
            if 'transcript' in data:
                print("Found 'transcript' key")
                if isinstance(data['transcript'], list):
                    print(f"Transcript contains {len(data['transcript'])} segments")
                    if data['transcript']:
                        first_segment = data['transcript'][0]
                        print(f"First segment keys: {list(first_segment.keys())}")
                        print(f"First segment: {first_segment}")
        
        elif isinstance(data, list):
            print(f"Top level is a list with {len(data)} items")
            if data:
                first_item = data[0]
                print(f"First item type: {type(first_item)}")
                if isinstance(first_item, dict):
                    print(f"First item keys: {list(first_item.keys())}")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    return False

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        test_transcript(sys.argv[1])
    else:
        print("Please provide a file path as an argument")
