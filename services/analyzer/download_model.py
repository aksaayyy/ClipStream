"""Script to download and cache the sentence transformer model."""
import os
from sentence_transformers import SentenceTransformer

def main():
    """Download and cache the model."""
    model_name = "all-MiniLM-L6-v2"
    print(f"Downloading and caching model: {model_name}")
    
    # This will download the model and cache it in the default location
    model = SentenceTransformer(model_name)
    
    # Verify the model was loaded
    print(f"Model loaded successfully: {model}")
    
    # Test the model with a small example
    embeddings = model.encode("This is a test sentence.")
    print(f"Model test successful. Embedding shape: {embeddings.shape}")

if __name__ == "__main__":
    main()
