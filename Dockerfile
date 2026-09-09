FROM python:3.11-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Set environment for pip
ENV PIP_NO_CACHE_DIR=1
ENV PIP_USER=0

# Copy only requirements first (for better caching)
COPY requirements.txt .

# Install dependencies in separate layers for better caching
# Layer 1: Upgrade pip
RUN pip install --upgrade pip

# Layer 2: Install numpy (pinned version, benefits most from caching)
RUN pip install numpy==1.26.4

# Layer 3: Install PyTorch with CUDA support (large packages, cache critical)
RUN pip install torch==2.2.0+cu121 torchvision==0.17.0+cu121 --extra-index-url https://download.pytorch.org/whl/cu121

# Layer 4: Install core web dependencies explicitly to ensure availability
RUN pip install --no-cache-dir fastapi==0.111.0 uvicorn[standard]==0.30.0

# Layer 5: Install remaining requirements (opencv, utils, etc.)
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim-bookworm AS runtime

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/celery /usr/local/bin/celery

# Copy source code (this layer will rebuild on code changes, but dependencies stay cached)
COPY src/ ./src/
COPY models/ ./models/

# Ensure storage directories exist
RUN mkdir -p storage/clips storage/db storage/nvr storage/logs

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# Run both CV pipeline and FastAPI server
ENTRYPOINT ["/entrypoint.sh"]
