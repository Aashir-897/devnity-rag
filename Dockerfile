FROM python:3.11-slim

# System dependencies for PaddleOCR (Updated for Debian Trixie/Slim)
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (UID 1000 — Hugging Face Spaces default)
RUN groupadd -g 1000 user && \
    useradd -m -u 1000 -g 1000 user

WORKDIR /app

# Pre-create writable folders and set ownership to user 1000
RUN mkdir -p /app/storage/temp /app/storage/images /app/vector_db && \
    chown -R 1000:1000 /app

# Switch to user 1000 before copying files
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Python dependencies (layer caching)
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Application code
COPY --chown=user:user . .

# Hugging Face Spaces exposes only port 7860
ENV PORT=7860
ENV HOST=0.0.0.0

EXPOSE 7860

CMD ["python", "app.py"]