FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed by some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Expose the port Render will use
EXPOSE 8000

# Start with uvicorn — single worker is fine for Render free tier
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
