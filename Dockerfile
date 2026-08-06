FROM python:3.11-slim-bookworm

# Install system dependencies: FFmpeg, OpenCV deps, minimal build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/
COPY models/ ./models/

# Ensure storage directories exist
RUN mkdir -p storage/clips storage/db storage/nvr

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Default: run the CV pipeline
CMD ["python", "-m", "src.main"]
