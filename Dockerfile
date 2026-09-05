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

# Set numpy version before installing torch to avoid conflicts
ENV PIP_NO_CACHE_DIR=1

# Copy and install requirements
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install numpy==1.26.4 --no-cache-dir && \
    pip install torch==2.2.0+cu121 torchvision==0.17.0+cu121 --extra-index-url https://download.pytorch.org/whl/cu121 --no-cache-dir && \
    pip install opencv-python-headless Pillow python-dotenv ultralytics filterpy scipy open3d fastapi uvicorn sqlalchemy alembic pydantic pydantic-settings streamlit ffmpeg-python loguru orjson celery redis websockets python-jose passlib python-multipart slowapi pytest pytest-cov pytest-asyncio httpx prometheus-client --no-cache-dir

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
COPY --from=builder /root/.local /root/.local
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
ENV PATH=/root/.local/bin:$PATH

# Copy source code
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
