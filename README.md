# 🎬 ClipStream - YouTube to Viral Shorts Generator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-✓-blue.svg)](https://www.docker.com/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A high-performance, modular system for auto-generating viral short-form content from YouTube videos. ClipStream provides an end-to-end pipeline for downloading, transcribing, analyzing, and rendering engaging video clips at scale.

## 🚀 Features

- **Multi-service Architecture**: Microservices for each stage of the pipeline
- **High-Quality Output**: Support for up to 4K video downloads
- **AI-Powered**: Uses OpenAI's Whisper for accurate speech-to-text
- **Scalable**: Containerized with Docker for easy deployment
- **Developer Friendly**: Modern Python with type hints and comprehensive testing
- **Customizable**: Flexible configuration for different use cases

## 📦 Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.8+
- FFmpeg (for local development)
- Git LFS (for handling large files)
- At least 8GB RAM (16GB recommended for better performance)

### Installation

1. **Clone the repository**
   ```bash
   git clone git@github.com:aksaayyy/ClipStream.git
   cd ClipStream
   ```

2. **Set up Git LFS**
   ```bash
   git lfs install
   ```

3. **Start the services**
   ```bash
   docker-compose up -d
   ```
   
   Wait for all services to be healthy. You can check status with:
   ```bash
   docker-compose ps
   ```

4. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   
   For development, also install:
   ```bash
   pip install -r requirements-dev.txt
   pre-commit install
   ```

## 🎬 Main Entry Point: process_video.py

The primary way to process videos through the ClipStream pipeline is using `process_video.py`. This script handles the entire workflow from downloading to rendering clips.

### Basic Usage

```bash
# Process a YouTube video through the entire pipeline
python process_video.py "https://www.youtube.com/watch?v=VIDEO_ID"

# Force re-download even if video exists
python process_video.py --force "https://www.youtube.com/watch?v=VIDEO_ID"

# Specify output directory
python process_video.py --output-dir ./my_clips "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Advanced Options

```bash
# Show all available options
python process_video.py --help

# Process with custom settings
python process_video.py \
    --chunk-duration 300 \
    --whisper-model tiny \
    --top-clips 3 \
    "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Checking Service Status

```bash
# Check health of all services
python clipstream.py check-health

# Check individual service
curl http://localhost:8001/health  # yt-fetcher
curl http://localhost:5002/health  # transcriber
curl http://localhost:5003/health  # analyzer
curl http://localhost:8080/health  # clip-renderer
```

## 🛠 Development

### Project Structure

```
ClipStream/
├── process_video.py        # Main entry point for video processing
├── clipstream.py           # CLI tool for service management
├── services/               # Microservices
│   ├── yt-fetcher/         # YouTube download service
│   ├── transcriber/        # Speech-to-text service
│   ├── analyzer/           # Content analysis service
│   └── clip-renderer/      # Video processing service
├── data/                   # Data directory (downloads, transcripts, clips)
│   ├── downloads/         # Downloaded videos
│   ├── transcripts/       # Generated transcripts
│   └── clips/             # Rendered video clips
├── tests/                  # Test suite
└── docker-compose.yml      # Production compose
```

### Environment Variables

Configure the system using these environment variables in a `.env` file:

```env
# Base directories
BASE_DIR=./data
DOWNLOAD_DIR=${BASE_DIR}/downloads
TRANSCRIPTS_DIR=${BASE_DIR}/transcripts
CLIPS_DIR=${BASE_DIR}/clips
FINAL_DIR=${BASE_DIR}/final

# Service URLs (defaults to localhost)
YT_FETCHER_URL=http://localhost:8001
TRANSCRIBER_URL=http://localhost:5002
ANALYZER_URL=http://localhost:5003
RENDERER_URL=http://localhost:8080

# Performance settings
MAX_WORKERS=4
CHUNK_DURATION=600  # 10 minutes
WHISPER_MODEL=tiny  # tiny, base, small, medium, large
TOP_CLIPS=5

# Timeouts (in seconds)
DOWNLOAD_TIMEOUT=1800
TRANSCRIBE_TIMEOUT=3600
ANALYZE_TIMEOUT=600
RENDER_TIMEOUT=1800
```

### Code Style

We use:
- Black for code formatting
- isort for import sorting
- flake8 for linting
- mypy for type checking

Pre-commit hooks are set up to enforce these standards:

```bash
# Install pre-commit hooks
pre-commit install

# Run checks manually
pre-commit run --all-files
```

### Testing

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=services --cov-report=term-missing
```

## 🚨 Troubleshooting

### Common Issues

1. **Service Not Starting**
   - Check Docker logs: `docker-compose logs <service_name>`
   - Verify ports are available
   - Ensure sufficient system resources (CPU, RAM, disk space)

2. **Video Download Fails**
   - Check internet connection
   - Verify YouTube video is available in your region
   - Try with `--force` flag to re-download

3. **Transcription Fails**
   - Check if Whisper model is downloaded
   - Increase `TRANSCRIBE_TIMEOUT` for long videos
   - Try a smaller model (e.g., `--whisper-model tiny`)

4. **Analysis Timeout**
   - Increase `ANALYZE_TIMEOUT`
   - Reduce `TOP_CLIPS` value
   - Check analyzer service logs

5. **Rendering Issues**
   - Verify FFmpeg is installed
   - Check available disk space
   - Ensure proper permissions on output directories

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please make sure to:
- Update tests as appropriate
- Add documentation for new features
- Follow the existing code style
- Update the CHANGELOG.md if applicable

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Feature-rich YouTube downloader
- [OpenAI Whisper](https://github.com/openai/whisper) - Speech recognition
- [FFmpeg](https://ffmpeg.org/) - Audio/video processing
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [Docker](https://www.docker.com/) - Container platform

## ✨ Features

### 🎥 YouTube Fetcher Service
- High-quality YouTube video downloads (up to 4K)
- Smart duplicate detection to avoid re-downloading
- REST API with rate limiting and request tracking
- Configurable download directory and quality settings
- Automatic format detection and conversion
- Health monitoring and logging

### 🎤 Transcriber Service
- Automatic speech-to-text using OpenAI's Whisper
- Support for multiple Whisper models (tiny, base, small, medium, large)
- Multi-language support with auto-detection
- Word-level timestamps for precise captioning
- Docker-ready with minimal configuration
- Automatic model downloading and caching

### ✂️ Clip Renderer Service
- Automatic clip generation from timestamps
- Customizable caption styling and positioning
- Audio normalization for consistent volume
- Vertical (9:16) and horizontal (16:9) output formats
- Hardware-accelerated video processing
- Progress tracking for long-running operations

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.8+ (for CLI tool)
- FFmpeg (for local development)
- Minimum 4GB RAM (8GB recommended)
- 10GB free disk space (for models and temporary files)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ClipStream.git
   cd ClipStream
   ```

2. Start the services:
   ```bash
   docker-compose up -d
   ```

3. Install the CLI tool:
   ```bash
   pip install -r requirements-cli.txt
   chmod +x clipstream.py
   ```

4. Verify the installation:
   ```bash
   ./clipstream.py check-health
   ```

## 🖥️ CLI Usage

The `clipstream.py` script is your main interface for interacting with ClipStream. It provides a simple yet powerful way to process videos through the entire pipeline.

### Basic Workflow

1. **Download a video**:
   ```bash
   ./clipstream.py download "https://www.youtube.com/watch?v=pSLZ4_2lcJo"
   ```

2. **Check processing status**:
   ```bash
   ./clipstream.py status
   ```

3. **List processed clips**:
   ```bash
   ./clipstream.py list-clips
   ```

### 🔧 Commands

#### Video Processing
```bash
# Basic download and process
./clipstream.py process "https://youtu.be/VIDEO_ID"

# Specify output format (vertical/horizontal)
./clipstream.py process --format vertical "https://youtu.be/VIDEO_ID"

# Process with custom clip duration (in seconds)
./clipstream.py process --max-duration 60 "https://youtu.be/VIDEO_ID"
```

#### Service Management
```bash
# Check service health
./clipstream.py check-health

# View service logs
./clipstream.py logs

# Restart services
./clipstream.py restart
```

#### Advanced Options
```bash
# Custom API endpoint
./clipstream.py --api http://localhost:8000 process "https://youtu.be/VIDEO_ID"

# Enable debug output
./clipstream.py --debug process "https://youtu.be/VIDEO_ID"

# View detailed help
./clipstream.py --help
./clipstream.py --debug download "https://youtu.be/VIDEO_ID"
```

## 🐳 Docker Deployment

Run the complete ClipStack with both yt-fetcher and transcriber services:

```bash
docker-compose up --build -d
```

### Environment Variables for Transcriber Service

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_MODEL` | `base` | Whisper model to use (tiny, base, small, medium, large) |
| `DOWNLOAD_DIR` | `/data/downloads` | Directory containing input audio/video files |
| `TRANSCRIPTS_DIR` | `/data/transcripts` | Directory to save transcript JSON files |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## 🎤 Transcriber Service

The transcriber service uses OpenAI's Whisper model to convert audio/video files to text with timestamps.

### API Endpoints

- `POST /api/v1/transcribe` - Transcribe an audio/video file
  ```json
  {
    "filename": "example.mp3",
    "language": "en",
    "model": "base"
  }
  ```
  
  Response:
  ```json
  {
    "success": true,
    "transcript": [
      {
        "start": 0.0,
        "end": 5.2,
        "text": "This is a sample transcription."
      }
    ],
    "language": "en",
    "duration": 5.2,
    "duration_formatted": "00:00:05",
    "file_path": "/data/transcripts/example.json"
  }
  ```

- `GET /health` - Service health check
- `GET /` - Service information

### Available Whisper Models

| Model | Parameters | Disk Size | Relative Speed |
|-------|------------|-----------|----------------|
| tiny  | 39M        | ~75MB     | ~32x           |
| base  | 74M        | ~142MB    | ~16x           |
| small | 244M       | ~466MB    | ~6x            |
| medium| 769M       | ~1.5GB    | ~2x            |
| large | 1550M      | ~3GB      | 1x             |

> Note: Larger models provide better accuracy but require more disk space and processing time.

### Manual Model Download

If you encounter SSL issues during automatic model download, you can manually download the model:

## 🐳 Docker Deployment

ClipStream is designed to run in Docker containers for easy deployment and scaling.

### Starting Services
```bash
# Start all services in detached mode
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Service Ports
- **yt-fetcher**: 8000
- **transcriber**: 5002
- **clip-renderer**: 8080
- **Redis**: 6379

### Environment Variables
Configure services using `.env` file:
```env
# YouTube Fetcher
YT_MAX_FILE_SIZE_MB=500
YT_MAX_VIDEO_LENGTH=3600

# Transcriber
WHISPER_MODEL=base
LANGUAGE=en

# Clip Renderer
OUTPUT_FORMAT=vertical
CAPTION_FONT=Arial
```

## 🛠️ Development

### Prerequisites
- Python 3.8+
- FFmpeg
- Redis
- Docker and Docker Compose

### Setup
1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
3. Start development services:
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```
4. Run tests:
   ```bash
   pytest tests/
   ```

### Project Structure
```
ClipStream/
├── services/               # Microservices
│   ├── yt-fetcher/         # YouTube download service
│   ├── transcriber/        # Speech-to-text service
│   └── clip-renderer/      # Video processing service
├── tests/                  # Test suite
├── docker-compose.yml       # Production compose
├── docker-compose.dev.yml   # Development compose
└── clipstream.py           # Main CLI tool
```

## 📚 Documentation

### API Reference
Detailed API documentation is available at `http://localhost:8000/docs` when services are running.

### Example Workflows

#### Basic Video Processing
```bash
# Download and process a video
./clipstream.py process "https://youtu.be/pSLZ4_2lcJo"

# View generated clips
ls -lh rendered_clips/
```

#### Batch Processing
```bash
# Process multiple videos
for url in \
  "https://youtu.be/video1" \
  "https://youtu.be/video2" \
  "https://youtu.be/video3"
do
  ./clipstream.py process "$url"
done
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Feature-rich YouTube downloader
- [OpenAI Whisper](https://github.com/openai/whisper) - Speech recognition
- [FFmpeg](https://ffmpeg.org/) - Audio/video processing
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [Docker](https://www.docker.com/) - Container platform

2. The model will be cached in `~/.cache/whisper/`

## 🌐 API Reference

### Endpoints

- `POST /fetch` - Download a YouTube video
  ```json
  {
    "url": "https://www.youtube.com/watch?v=...",
    "format": "mp4",
    "request_id": "unique-request-id"
  }
  ```

- `GET /info?url=YOUTUBE_URL` - Get video info without downloading
- `GET /health` - Service health check

## 🔄 End-to-End Workflow

### 1. Download a YouTube Video
```bash
./clipstream.py download --url "https://www.youtube.com/watch?v=example"
```

### 2. Transcribe the Video
```bash
./clipstream.py transcribe --input /path/to/video.mp4
```

### 3. Preprocess the Transcript (if needed)
```bash
python preprocess_transcript.py /path/to/transcript.json
```

### 4. Analyze the Transcript
```bash
curl -X POST "http://localhost:5003/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -d '{"filename": "transcript_preprocessed.json"}'
```

### Example Response
```json
{
  "success": true,
  "video": "transcript_preprocessed.json",
  "language": "en",
  "total_duration": "00:02:51",
  "recommended_clips": [
    {
      "start": 14.28,
      "end": 24.48,
      "text": "example text",
      "score": 0.9,
      "reason": "high engagement, emotional content"
    }
  ]
}
```

## 🎬 Clip Analyzer API

### Endpoints

#### POST /api/v1/analyze
Analyze a transcript and return recommended clips.

**Request Body:**
```json
{
  "filename": "path/to/transcript.json"
}
```

**Response:**
```json
{
  "success": true,
  "video": "filename.json",
  "language": "en",
  "total_duration": "HH:MM:SS",
  "recommended_clips": [
    {
      "start": 0.0,
      "end": 10.5,
      "text": "transcript text",
      "score": 0.85,
      "reason": "high engagement"
    }
  ]
}
```

#### GET /health
Check service health.

**Response:**
```json
{
  "status": "healthy",
  "service": "clip-analyzer",
  "version": "0.1.0"
}
```

Here's how to use ClipStream to download and transcribe a YouTube video:

1. **Start the services**:
   ```bash
   docker-compose up -d yt-fetcher transcriber
   ```

2. **Download a video** using the CLI:
   ```bash
   python clipstream.py download "https://www.youtube.com/watch?v=VIDEO_ID"
   ```
   
   Example:
   ```bash
   python clipstream.py download "https://www.youtube.com/watch?v=xdr_cX5NQV8"
   ```

3. **Transcribe the video** using the API:
   ```bash
   curl -X POST "http://localhost:5002/api/v1/transcribe" \
     -H "Content-Type: application/json" \
     -d '{"filename": "VIDEO_FILENAME.mp4"}'
   ```
   
   Example:
   ```bash
   curl -X POST "http://localhost:5002/api/v1/transcribe" \
     -H "Content-Type: application/json" \
     -d '{"filename": "AMG_xdr_cX5NQV8.mp4"}'
   ```

4. **Check the transcription**:
   - The transcript will be saved to `/data/transcripts/` in the container
   - You can access it via the API response or directly from the container

## 🔧 Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DOWNLOAD_DIR` | `./downloads` | Directory to save downloaded videos |
| `MAX_FILE_SIZE_MB` | `500` | Maximum allowed file size in MB |
| `RATE_LIMIT` | `100` | Max requests per day per IP |

## 🐞 Troubleshooting

### Common Issues

1. **Video quality not optimal**
   - Ensure FFmpeg is installed and in your PATH
   - Check available formats with: `yt-dlp -F URL`

2. **Download fails with "Duplicate request"**
   - Use `--force` flag to override
   - Check active downloads in the service logs

3. **Transcription fails with SSL errors**
   - Try manually downloading the model using the script above
   - Ensure your system has proper SSL certificates installed
   - Set `REQUESTS_CA_BUNDLE` environment variable if using a custom CA

4. **Model download is slow**
   - The first run will download the model (142MB for 'base' model)
   - Subsequent runs will use the cached model
   - For production, consider pre-downloading the model in your Dockerfile

5. **Service not starting**
   - Check logs: `docker-compose logs transcriber`
   - Verify ports 5002 (transcriber) and 8000 (yt-fetcher) are available
   - Ensure sufficient disk space for models (at least 2GB recommended)

### Logs

View transcriber service logs:
```bash
docker-compose logs -f transcriber
```

### Testing the Transcriber

Use the test script to verify the transcriber:

```bash
# Navigate to the transcriber directory
cd services/transcriber

# Run the test script
python3 test_transcription.py output/sample.mp3 --model base

# For a different language
python3 test_transcription.py path/to/spanish.mp3 --language es
```

## Development

### Running Tests

```bash
# Install test requirements
pip install -r services/transcriber/requirements-dev.txt

# Run tests
pytest services/transcriber/tests/
```

### Adding New Features

## 🚀 Quick Start for Developers

1. **Clone and setup**
   ```bash
   git clone https://github.com/yourusername/ClipStream.git
   cd ClipStream
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   pip install -r requirements-dev.txt
   ```

2. **Start development services**
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

3. **Run tests**
   ```bash
   pytest tests/ -v
   ```

4. **Make changes**
   - Follow the project's code style (PEP 8)
   - Write tests for new features
   - Update documentation

5. **Submit a PR**
   - Create a descriptive pull request
   - Reference any related issues
   - Include test results

## 📝 Code of Conduct

Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for details on our code of conduct.

## 📧 Contact

Project Link: [https://github.com/yourusername/ClipStream](https://github.com/yourusername/ClipStream)

## 📊 Project Status

Active Development - New features and improvements are being added regularly.
6. Submit a pull request

## 📝 License

MIT License - Feel free to contribute!

## 🙏 Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) for the amazing speech recognition model
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for YouTube video downloads
- [FastAPI](https://fastapi.tiangolo.com/) for the web framework
- [Docker](https://www.docker.com/) for containerization

## 📚 Resources

- [Whisper Paper](https://cdn.openai.com/papers/whisper.pdf)
- [Whisper GitHub](https://github.com/openai/whisper)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Documentation](https://docs.docker.com/)

## 🗂️ Project Structure

```
clipstream/
├── clipstream.py          # Main CLI interface
├── run.sh                  # Service management script
├── docker-compose.yml      # Docker Compose configuration
├── README.md              # This file
├── .gitignore
└── services/
    └── yt-fetcher/        # YouTube fetcher service
        ├── Dockerfile      # Container definition
        ├── requirements.txt
        ├── yt-fetcher.log  # Log file
        └── app/
            ├── __init__.py
            ├── main.py     # FastAPI application
            ├── models.py   # Pydantic models
            └── utils.py    # Helper functions
```

## Getting Started

### Prerequisites

- Docker
- Docker Compose

### Running the Service

1. Clone the repository
2. Navigate to the project root
3. Run: `docker-compose up --build`

### API Endpoints

- `POST /fetch`: Download a YouTube video
  ```json
  {
    "url": "https://www.youtube.com/watch?v=..."
  }
  ```

- `GET /health`: Service health check

### Environment Variables

- `DOWNLOAD_DIR`: Directory to save downloaded videos (default: `/data/downloads`)

## Development

1. Create a virtual environment: `python -m venv venv`
2. Activate it: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
3. Install dependencies: `pip install -r services/yt-fetcher/requirements.txt`
4. Run the service: `uvicorn services.yt-fetcher.app.main:app --reload`
