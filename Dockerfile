FROM python:3.11-slim

# System dependencies for PaddleOCR
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user (UID 1000 — Hugging Face Spaces default)
RUN groupadd -g 1000 user && \
    useradd -m -u 1000 -g 1000 user

WORKDIR /app

# Python dependencies (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Create writable runtime directories for user 1000
RUN mkdir -p /app/storage/temp /app/storage/images /app/vector_db && \
    chown -R 1000:1000 /app/storage /app/vector_db

USER 1000

# Hugging Face Spaces exposes only port 7860
ENV PORT=7860
ENV HOST=0.0.0.0

EXPOSE 7860

CMD ["python", "app.py"]
