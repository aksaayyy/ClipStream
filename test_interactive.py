import requests
import json

def print_response(response):
    """Print the response in a formatted way"""
    print("\n=== Response ===")
    print(f"Status Code: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)
    print("=" * 20 + "\n")

def main():
    print("ClipStream YouTube Video Fetcher")
    print("Enter 'q' to quit\n")
    
    while True:
        # Get YouTube URL from user
        url = input("Enter YouTube URL (or 'q' to quit): ").strip()
        
        if url.lower() == 'q':
            print("Goodbye!")
            break
            
        if not url:
            print("Please enter a valid URL\n")
            continue
            
        try:
            # Make the API request
            print(f"\nFetching video: {url}")
            response = requests.post(
                "http://127.0.0.1:8000/fetch",
                json={"url": url}
            )
            
            # Print the response
            print_response(response)
            
        except requests.exceptions.RequestException as e:
            print(f"\nError: {e}")
            print("Make sure the server is running on http://127.0.0.1:8000\n")
        except Exception as e:
            print(f"\nAn unexpected error occurred: {e}\n")

if __name__ == "__main__":
    main()
