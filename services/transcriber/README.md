# ClipStream Transcriber Service

A FastAPI-based microservice for transcribing audio and video files using OpenAI's Whisper model. This service is part of the ClipStream pipeline and is designed to work with the yt-fetcher service.

## Features

- Transcribe audio/video files to text with timestamps
- Support for multiple audio/video formats
- Configurable Whisper models (tiny, base, small, medium, large)
- RESTful API with OpenAPI documentation
- Containerized with Docker for easy deployment
- Health check endpoint for monitoring

## Prerequisites

- Python 3.10+
- Docker and Docker Compose
- FFmpeg (for audio processing)

## Getting Started

### Local Development

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd services/transcriber
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

4. Run the service locally:
   ```bash
   uvicorn app.main:app --reload --port 5002
   ```

### Using Docker

1. Build and start the service using Docker Compose:
   ```bash
   docker-compose up --build
   ```

2. The service will be available at `http://localhost:5002`

## API Documentation

Once the service is running, you can access the following endpoints:

- `GET /` - Service information
- `GET /health` - Health check
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)
- `POST /api/v1/transcribe` - Transcribe an audio/video file

### Transcribe Endpoint

```http
POST /api/v1/transcribe
Content-Type: application/json

{
  "filename": "example.mp3",
  "language": "en",
  "model": "base"
}
```

#### Response

```json
{
  "success": true,
  "transcript": [
    {
      "start": 0.0,
      "end": 5.0,
      "text": "This is a sample transcription."
    }
  ],
  "language": "en",
  "duration": 5.0,
  "duration_formatted": "00:00:05",
  "file_path": "/data/transcripts/example.json"
}
```

## Configuration

The service can be configured using environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Host to bind the server to |
| `PORT` | `5002` | Port to run the server on |
| `DOWNLOAD_DIR` | `/data/downloads` | Directory containing input files |
| `TRANSCRIPTS_DIR` | `/data/transcripts` | Directory to save transcript files |
| `WHISPER_MODEL` | `base` | Whisper model to use (tiny, base, small, medium, large) |
| `ENV` | `development` | Environment (development, production) |

## Testing

Run the test suite:

```bash
pytest tests/
```

Or use the test script:

```bash
python test_transcriber.py
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
