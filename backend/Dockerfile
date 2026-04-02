FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Java for PySpark
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    openjdk-11-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME environment variable
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
