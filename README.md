# ClipStream

An AI video processing pipeline that turns YouTube videos into short-form clips: download, transcribe, analyze for engaging moments, and render ready-to-publish videos.

## Overview

ClipStream automates the production of short-form content from long YouTube videos. It is built as a set of modular FastAPI microservices, each responsible for one stage of the pipeline: downloading the source video, transcribing its audio with OpenAI Whisper, scoring the transcript to select the most engaging segments, and rendering those segments into vertical or square clips with captions and normalized audio.

The services communicate through a shared data volume (`./data` mounted at `/data` in the containers) and a simple REST interface. A CLI entry point, `process_video.py`, drives the full pipeline end to end.

## Architecture

The pipeline is split into four services, orchestrated by the root-level compose file and the CLI:

```
   YouTube
      |
      v
+------------------+
|   yt-fetcher     |  Downloads the source video with yt-dlp
|  (FastAPI, 8001) |  Validates size, length and availability
+------------------+
      |
      v  shared volume: /data/downloads
+------------------+
|   transcriber    |  Speech-to-text with OpenAI Whisper
|  (FastAPI, 5002) |  Produces timestamped transcript segments
+------------------+
      |
      v  shared volume: /data/transcripts
+------------------+
|     analyzer     |  Scores segments (hooks, emotion, pacing)
|  (FastAPI, 5003) |  Selects non-overlapping top clips
+------------------+
      |
      v  shared volume: /data/clips
+------------------+
|  clip-renderer   |  Cuts segments with FFmpeg, adds captions,
|  (FastAPI, 8080) |  normalizes audio, writes final clips
+------------------+
      |
      v
   Rendered clips (vertical / square / original)
```

`docker-compose.yml` defines the `yt-fetcher`, `transcriber`, and `clip-renderer` services and the shared data volume. The `analyzer` ships with its own `docker-compose.yml` in `services/analyzer` because it needs dedicated model caches.

### Services

- **yt-fetcher** (`services/yt-fetcher`) - Downloads YouTube videos with yt-dlp, exposes download status tracking, duplicate detection, and per-request rate limiting.
- **transcriber** (`services/transcriber`) - Converts downloaded audio to timestamped transcripts using OpenAI Whisper. Configurable model size, language auto-detection, and word-level timestamps.
- **analyzer** (`services/analyzer`) - Scores transcript segments using hook-phrase detection, emotional keywords, pacing, duration, and sentence-transformer embeddings, then selects the top non-overlapping clips.
- **clip-renderer** (`services/clip-renderer`) - Renders selected segments with FFmpeg into vertical (9:16), square (1:1), or original-aspect clips, adds optional captions, and normalizes audio to broadcast loudness levels.

## Features

- End-to-end pipeline from a YouTube URL to rendered clips in a single command
- Timestamped transcription with OpenAI Whisper (tiny through large models)
- Engagement scoring that combines lexical hooks, sentiment, pacing, and semantic embeddings
- Non-overlapping clip selection with configurable duration and count limits
- FFmpeg rendering with caption overlay and loudness normalization
- Vertical, square, and original aspect ratio outputs
- Containerized services with Docker Compose and a shared data volume
- Per-service health checks and request logging

## Tech Stack

- Python 3.8+
- FastAPI and Uvicorn for the service APIs
- OpenAI Whisper for speech-to-text
- yt-dlp for YouTube downloads
- FFmpeg / FFprobe for media processing
- sentence-transformers and NLTK for transcript analysis
- Docker and Docker Compose for orchestration

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.8+ (for running the CLI locally)
- FFmpeg (for local development outside Docker)
- ~8 GB RAM recommended (the Whisper model and analyzer embeddings are memory-intensive)

### Running with Docker Compose

```bash
git clone https://github.com/aksaayyy/ClipStream.git
cd ClipStream
docker-compose up -d
docker-compose ps
```

The `docker-compose.yml` file defines the `yt-fetcher`, `transcriber`, and `clip-renderer` services. To include the analyzer, run it from its own directory:

```bash
cd services/analyzer
docker-compose up -d
```

The analyzer expects an external `clipstream_shared_data` volume and a `clipstream_clipstream_network` network; create them first if they do not exist:

```bash
docker volume create clipstream_shared_data
docker network create clipstream_clipstream_network
```

### Running Services Locally

Each service can be run directly with Uvicorn. See the README in each service directory for service-specific setup:

```bash
# yt-fetcher (port 8001)
uvicorn app.main:app --host 0.0.0.0 --port 8000   # from services/yt-fetcher

# transcriber (port 5002)
uvicorn app.main:app --host 0.0.0.0 --port 5002   # from services/transcriber

# analyzer (port 5003)
uvicorn app.main:app --host 0.0.0.0 --port 5003   # from services/analyzer

# clip-renderer (port 5004)
uvicorn app.main:app --host 0.0.0.0 --port 5004   # from services/clip-renderer
```

Install dependencies per service with `pip install -r requirements.txt` from the relevant directory. For development dependencies shared across the project, install `requirements-dev.txt` at the repository root.

### Processing a Video

With all services running, process a video end to end:

```bash
python process_video.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

Or use the CLI for a single stage:

```bash
python clipstream.py check-health
python clipstream.py download "https://www.youtube.com/watch?v=VIDEO_ID"
```

`run.sh` is a small process manager for running `yt-fetcher` as a background process during development (`./run.sh start|stop|status|logs`).

## Testing

The project uses pytest. Each service keeps its tests in its own `tests/` directory:

```bash
pytest services/analyzer/tests/
pytest services/transcriber/tests/
pytest services/clip-renderer/tests/
```

Service-level test dependencies are listed in each service's `requirements.txt`. `test-requirements.txt` at the root provides the shared test dependencies (`requests`, `pytest`). The repository root also contains a `tests/` directory with manual scripts that exercise individual services against a running stack (for example, `tests/test_yt_fetcher.py` and `tests/test_ytdlp.py`).

Pre-commit hooks enforce formatting and linting:

```bash
pip install -r requirements-dev.txt
pre-commit install
pre-commit run --all-files
```

## API Endpoints

### yt-fetcher (default host port 8001)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/fetch` | Download a YouTube video. Body: `{"url": "...", "format": "mp4", "request_id": "..."}` |
| GET | `/info?url=...` | Get video metadata without downloading |
| GET | `/health` | Health check |

### transcriber (port 5002)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/transcribe` | Transcribe an audio/video file. Body: `{"filename": "video.mp4", "language": "en", "model": "base"}` |
| GET | `/health` | Health check |
| GET | `/` | Service information |

### analyzer (port 5003)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/analyze` | Analyze a transcript and return recommended clips. Provide either `{"filename": "transcript.json"}` (file in `/data/transcripts`) or `{"segments": [{"start": 0.0, "end": 5.0, "text": "..."}]}`. Optional params: `min_clip_duration`, `max_clip_duration`, `top_k`, `language` |
| GET | `/health` | Health check |
| GET | `/` | Service information |

### clip-renderer (default host port 8080)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/render` | Render clips. Body: `{"video": "video.mp4", "format": "vertical", "add_captions": true, "normalize_audio": true, "output_dir": "/data/final"}`. Expects `video`, `transcript`, and `{video}_clips.json` in the shared data volume |
| GET | `/video/{video_name}/info` | Get metadata for a video file in the downloads directory |
| GET | `/health` | Health check |

Interactive OpenAPI documentation is served at `/docs` for each service.

## Project Structure

```
ClipStream/
├── clipstream.py               CLI for downloading and health checks
├── process_video.py            End-to-end pipeline runner
├── run.sh                      Development process manager for yt-fetcher
├── docker-compose.yml          Compose definition for yt-fetcher, transcriber, clip-renderer
├── requirements-dev.txt        Shared development dependencies
├── test-requirements.txt       Shared test dependencies
├── tests/                      Manual service test scripts
├── services/
│   ├── yt-fetcher/             YouTube download service
│   │   └── app/
│   ├── transcriber/            Whisper transcription service
│   │   └── app/
│   ├── analyzer/               Transcript analysis and clip selection service
│   │   ├── app/
│   │   ├── tests/
│   │   └── docker-compose.yml
│   └── clip-renderer/          FFmpeg clip rendering service
│       ├── app/
│       └── tests/
├── .pre-commit-config.yaml
├── CONTRIBUTING.md
└── LICENSE
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
