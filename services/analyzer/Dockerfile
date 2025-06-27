# Use a specific version of Python for better reproducibility
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN adduser --disabled-password --gecos "" appuser

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with specific versions
RUN pip install --no-cache-dir -r requirements.txt numpy==1.26.0

# Copy the rest of the application
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /data/transcripts /data/clips /app/model_cache \
    && chown -R appuser:appuser /app /data \
    && chmod +x /app/download_model.py

# Download the model as root first
RUN python download_model.py

# Ensure the model cache is accessible to the appuser
RUN chown -R appuser:appuser /root/.cache

# Switch to non-root user
USER appuser

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TOKENIZERS_PARALLELISM=false
ENV HF_HOME=/app/model_cache
ENV TRANSFORMERS_CACHE=/app/model_cache
ENV HUGGINGFACE_HUB_CACHE=/app/model_cache

# Expose the port the app runs on
EXPOSE 5003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5003/health || exit 1

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5003", "--workers", "1"]
