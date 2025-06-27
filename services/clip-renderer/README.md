# Clip Renderer Service

A high-performance, containerized microservice for rendering professional-quality video clips with styled captions. Part of the ClipStream pipeline, this service transforms raw video segments into polished, platform-optimized clips ready for social media sharing.

## Features

- 🎬 **Smart Video Processing**
  - Precise frame-accurate cutting with FFmpeg
  - Support for multiple output formats (vertical, square, original)
  - Hardware-accelerated encoding (when available)
  - Automatic aspect ratio handling and padding

- 💬 **Professional Captioning**
  - Platform-optimized caption styles (YouTube, TikTok, Instagram)
  - Dynamic text wrapping and positioning
  - Smooth fade in/out transitions
  - Customizable fonts, colors, and effects

- 🔊 **Audio Enhancement**
  - Loudness normalization to broadcast standards (-16 LUFS)
  - Dynamic range compression
  - Audio ducking for voice clarity

- 🚀 **Scalable Architecture**
  - Containerized with Docker for easy deployment
  - RESTful API for seamless integration
  - Asynchronous processing for high throughput
  - Comprehensive logging and monitoring

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.9+
- FFmpeg 4.4+

### Running with Docker

```bash
# Build the container
docker-compose build

# Start the service
docker-compose up -d

# Check logs
docker-compose logs -f
```

### Local Development

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

3. Run the service locally:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 5004 --reload
   ```

## API Reference

### Render Video Clips

```http
POST /render
```

**Request Body:**

```json
{
  "video": "example.mp4",
  "format": "vertical",
  "add_captions": true,
  "normalize_audio": true,
  "output_dir": "/data/final"
}
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `video` | string | Name of the video file in the downloads directory |
| `format` | string | Output format: `vertical`, `square`, or `original` |
| `add_captions` | boolean | Whether to add captions (default: `true`) |
| `normalize_audio` | boolean | Whether to normalize audio levels (default: `true`) |
| `output_dir` | string | Custom output directory (default: `/data/final`) |

**Response:**

```json
{
  "success": true,
  "clips_rendered": [
    "/data/final/example_clip_1.mp4"
  ],
  "details": {
    "video": "example.mp4",
    "format": "vertical",
    "clips_rendered": 1
  }
}
```

### Get Video Information

```http
GET /video/{video_name}/info
```

**Response:**

```json
{
  "success": true,
  "video": {
    "filename": "example.mp4",
    "path": "/data/downloads/example.mp4",
    "duration": 3600.5,
    "duration_formatted": "01:00:00",
    "resolution": "1920x1080",
    "bitrate": "4000k"
  }
}
```

## Testing

### Unit Tests

```bash
# Run all tests
pytest tests/

# Run with coverage report
pytest --cov=app --cov-report=term-missing tests/
```

### Integration Tests

```bash
# Run end-to-end tests
python scripts/test_full_pipeline.py

# Keep intermediate files for inspection
python scripts/test_full_pipeline.py --keep-files

# Specify custom output directory
python scripts/test_full_pipeline.py --output-dir test_output
```

### Test Coverage

To generate a coverage report:

```bash
coverage run -m pytest
coverage report -m
coverage html  # Generate HTML report
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_DIR` | `/data` | Base directory for data storage |
| `LOG_LEVEL` | `INFO` | Logging level |
| `MAX_WORKERS` | `4` | Maximum number of worker processes |
| `FFMPEG_THREADS` | `0` | Number of threads for FFmpeg (0 = auto) |

### Video Formats

#### Vertical (9:16)
- Resolution: 1080x1920
- Optimized for: TikTok, Instagram Reels, YouTube Shorts
- Smart crop with padding
- Caption-safe areas

#### Square (1:1)
- Resolution: 1080x1080
- Optimized for: Instagram posts, Facebook
- Center crop
- Responsive text scaling

#### Original
- Maintains source aspect ratio
- Maximum resolution: 1920x1080
- Automatic bitrate adjustment

## Audio Processing

### Normalization
- Target loudness: -16 LUFS (EBU R128)
- True peak: -1.5 dBTP
- Dynamic range: 11 LU

### Processing Chain
1. Loudness normalization
2. Dynamic range compression
3. Peak limiting
4. Dithering

## Performance

### Benchmarks

| Operation | Avg. Time | Notes |
|-----------|-----------|-------|
| 30s clip (HD) | 8.2s | With captions and audio normalization |
| 60s clip (HD) | 14.7s | With captions and audio normalization |
| 30s clip (4K) | 22.4s | With captions and audio normalization |

### Optimization Tips

1. **Hardware Acceleration**
   - Enable GPU acceleration with `--enable-nvenc`
   - Use Intel Quick Sync with `-hwaccel qsv`

2. **Memory Management**
   - Increase worker count for parallel processing
   - Set appropriate memory limits in Docker

3. **Caching**
   - Enable filesystem caching for frequently used assets
   - Use a CDN for distributed delivery

## Deployment

### Docker Compose

```yaml
version: '3.8'

services:
  clip-renderer:
    build: .
    ports:
      - "5004:5004"
    volumes:
      - ./data:/data
    environment:
      - BASE_DIR=/data
      - LOG_LEVEL=INFO
      - MAX_WORKERS=4
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: clip-renderer
spec:
  replicas: 2
  selector:
    matchLabels:
      app: clip-renderer
  template:
    metadata:
      labels:
        app: clip-renderer
    spec:
      containers:
      - name: clip-renderer
        image: clip-renderer:latest
        ports:
        - containerPort: 5004
        resources:
          limits:
            cpu: "2"
            memory: "2Gi"
        volumeMounts:
        - name: data-volume
          mountPath: /data
      volumes:
      - name: data-volume
        persistentVolumeClaim:
          claimName: clip-renderer-data
```

## Monitoring

### Health Check

```http
GET /health
```

**Response:**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2023-07-20T12:00:00Z"
}
```

### Metrics

```
# HELP renderer_requests_total Total number of render requests
# TYPE renderer_requests_total counter
renderer_requests_total{status="success"} 42
renderer_requests_total{status="error"} 3

# HELP renderer_processing_seconds Time spent processing videos
# TYPE renderer_processing_seconds histogram
renderer_processing_seconds_bucket{le="5"} 12
renderer_processing_seconds_bucket{le="10"} 35
renderer_processing_seconds_bucket{le="+Inf"} 42
renderer_processing_seconds_sum 312.5
renderer_processing_seconds_count 42
```

## Troubleshooting

### Common Issues

1. **FFmpeg not found**
   ```
   Ensure FFmpeg is installed and in your PATH
   ```

2. **Permission denied**
   ```
   Check file permissions and ensure the service has write access to output directories
   ```

3. **Out of memory**
   ```
   Reduce the number of worker processes or increase container memory limits
   ```

### Logs

View logs with:

```bash
docker-compose logs -f
```

Or check the log file at `logs/clip-renderer.log`.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- FFmpeg team for the amazing multimedia framework
- Python community for excellent libraries
- ClipStream team for the opportunity

## Features

- 🎬 Cut video segments based on timestamps
- 📱 Convert to vertical (9:16), square (1:1), or original aspect ratio
- 💬 Add hardcoded subtitles from transcript files
- 🔊 Normalize audio levels for consistent playback
- 🐳 Docker container with FFmpeg included
- 🔄 REST API for easy integration

## API Endpoints

### `GET /health`
Check service health status.

### `GET /video/{video_name}/info`
Get information about a video file.

**Parameters:**
- `video_name`: Name of the video file in the downloads directory

**Example Response:**
```json
{
  "success": true,
  "video": {
    "filename": "example.mp4",
    "path": "/data/downloads/example.mp4",
    "duration": 3600.5,
    "duration_formatted": "01:00:00"
  }
}
```

### `POST /render`
Render video clips based on the provided video and clips configuration.

**Request Body:**
```json
{
  "video": "example.mp4",
  "format": "vertical",
  "add_captions": true,
  "normalize_audio": true,
  "output_dir": "/data/final"
}
```

**Parameters:**
- `video`: Name of the video file in the downloads directory (required)
- `format`: Output format - "vertical" (9:16), "square" (1:1), or "original" (default: "vertical")
- `add_captions`: Whether to add captions to the video (default: true)
- `normalize_audio`: Whether to normalize audio levels (default: true)
- `output_dir`: Custom output directory (default: "/data/final")

**Example Response:**
```json
{
  "success": true,
  "clips_rendered": [
    "/data/final/example_clip_1.mp4",
    "/data/final/example_clip_2.mp4"
  ],
  "details": {
    "video": "example.mp4",
    "format": "vertical",
    "clips_rendered": 2
  }
}
```

## Required Input Files

The service expects the following files to be present:

1. **Video File**
   - Path: `/data/downloads/{video_name}`
   - Format: Any format supported by FFmpeg (MP4, MKV, etc.)

2. **Transcript File**
   - Path: `/data/transcripts/{video_stem}.json`
   - Format: JSON with segments containing 'start', 'end', and 'text' fields

3. **Clips Configuration**
   - Path: `/data/clips/{video_stem}_clips.json`
   - Format: JSON with 'recommended_clips' array containing 'start' and 'end' times

## Output

Rendered clips are saved to the specified output directory (default: `/data/final`) with the naming pattern:
```
{video_stem}_clip_{n}.mp4
```

## Development

### Prerequisites

- Python 3.9+
- FFmpeg
- Docker (for containerized deployment)

### Local Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the service:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 5004 --reload
   ```

### Docker

Build and run the service using Docker:

```bash
docker build -t clip-renderer .
docker run -p 5004:5004 -v /path/to/data:/data clip-renderer
```

## Environment Variables

- `BASE_DIR`: Base directory for data (default: "/data")
- `LOG_LEVEL`: Logging level (default: "INFO")

## Testing

### Unit Tests

Run the unit test suite:

```bash
pytest tests/
```

### End-to-End Tests

For end-to-end testing, you'll need to install additional dependencies:

```bash
pip install yt-dlp pytest-cov
```

Then run the end-to-end test script:

```bash
# Basic test (will download a test video)
python scripts/test_end_to_end.py

# Keep intermediate files for inspection
python scripts/test_end_to_end.py --keep-files

# Specify custom output directory
python scripts/test_end_to_end.py --output-dir my_test_output
```

### Test Coverage

To generate a test coverage report:

```bash
pytest --cov=app --cov-report=term-missing tests/
```

## Video Format Options

The renderer supports three output formats:

1. **Vertical (9:16)** - Ideal for Instagram Reels, TikTok, and YouTube Shorts
   - Resolution: 1080x1920
   - Smart crop with padding if needed
   
2. **Square (1:1)** - Good for Instagram posts
   - Resolution: 1080x1080
   - Center-cropped
   
3. **Original** - Maintains source aspect ratio
   - Resolution: Same as source (up to 1080p)

## Audio Normalization

Audio is normalized using a two-stage process:

1. **Loudness Normalization**
   - Target integrated loudness: -16 LUFS
   - True peak: -1.5 dBTP
   - Loudness range: 11 LU

2. **Dynamic Normalization**
   - Frame size: 5 seconds
   - Peak target: 0.5

This ensures consistent audio levels across different clips and platforms.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.