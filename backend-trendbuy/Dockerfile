FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps required for Playwright and general build
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
       wget \
       gnupg \
       git \
       libnss3 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (with dependencies)
RUN python -m playwright install chromium --with-deps

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Default command (can be overridden by docker-compose for celery)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
