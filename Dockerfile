FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Install system dependencies needed for some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application
COPY . /app

# Expose web port
EXPOSE 8080

# Create non-root user and ensure application files are writable
RUN adduser --disabled-password --gecos '' appuser || true
RUN chown -R appuser:appuser /app || true
USER appuser

CMD ["python", "server.py"]
