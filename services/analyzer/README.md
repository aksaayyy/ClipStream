# Clip Analyzer Service

The Clip Analyzer Service is a core component of the ClipStream pipeline that analyzes video transcripts to identify and score the most engaging, viral-worthy moments in a video. It uses a combination of NLP techniques and heuristic scoring to find the best clips for short-form content.

## Features

- **Transcript Analysis**: Processes Whisper-generated transcript JSON files
- **Engagement Scoring**: Scores segments based on multiple factors:
  - Hook phrases that capture attention
  - Emotional content and intensity
  - Pacing and delivery
  - Segment duration
  - NLP-based semantic analysis
- **Non-overlapping Clip Selection**: Smartly selects the best non-overlapping clips
- **REST API**: Easy-to-use HTTP endpoints for integration
- **Docker Support**: Containerized for easy deployment

## Prerequisites

- Python 3.9+
- Docker (optional, for containerized deployment)
- Access to the internet for downloading ML models (first run)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd services/analyzer
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Running the Service

#### Development Mode
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 5003
```

#### Production Mode (with Docker)
```bash
docker build -t clip-analyzer .
docker run -d -p 5003:5003 --name clip-analyzer clip-analyzer
```

### API Endpoints

#### Health Check
```
GET /health
```

#### Analyze Transcript
```
POST /api/v1/analyze
```

**Request Body:**
```json
{
  "filename": "video123_transcript.json",
  "min_clip_duration": 10.0,
  "max_clip_duration": 60.0,
  "top_k": 5,
  "language": "en"
}
```

**Response:**
```json
{
  "success": true,
  "video": "video123",
  "language": "en",
  "total_duration": "00:10:30",
  "analyzed_at": "2023-11-01T12:00:00.000000",
  "recommended_clips": [
    {
      "start": 45.2,
      "end": 75.8,
      "text": "You won't believe what happens next in this amazing demonstration!",
      "score": 0.92,
      "reason": "contains engaging hook phrase, high emotional content"
    },
    ...
  ]
}
```

### Testing

Run the test suite:
```bash
pytest tests/
```

For manual testing, use the provided test script:
```bash
python test_analyzer.py
```

## Configuration

The service can be configured using environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `all-MiniLM-L6-v2` | Sentence transformer model to use |
| `LOG_LEVEL` | `INFO` | Logging level |
| `MAX_WORKERS` | `4` | Maximum number of worker processes |

## Development

### Project Structure

```
analyzer/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── routers/             # API endpoints
│   │   └── analyze.py
│   ├── services/            # Business logic
│   │   ├── __init__.py
│   │   └── analyzer_service.py
│   └── models/              # Pydantic models
│       └── __init__.py
├── tests/                   # Test files
│   └── test_analyzer.py
├── test_analyzer.py         # Manual test script
├── requirements.txt          # Python dependencies
├── Dockerfile               # Container configuration
└── README.md                # This file
```

### Adding New Features

1. Create a new branch: `git checkout -b feature/new-feature`
2. Make your changes
3. Add tests for your changes
4. Run tests: `pytest`
5. Commit your changes: `git commit -am 'Add new feature'`
6. Push to the branch: `git push origin feature/new-feature`
7. Create a pull request

## License

[Your License Here]

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting pull requests.

## Support

For support, please open an issue in the repository or contact the maintainers.
