FROM python:3.11-slim-bookworm

WORKDIR /app

# Install system dependencies including Java for PySpark
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    openjdk-17-jdk-headless \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME environment variable
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-arm64

# Download Spark JDBC/ S3 jars
ENV SPARK_JARS_DIR=/opt/spark/jars
RUN mkdir -p ${SPARK_JARS_DIR} && \
    curl -fSL -o ${SPARK_JARS_DIR}/postgresql-42.7.1.jar \
        https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.1/postgresql-42.7.1.jar && \
    curl -fSL -o ${SPARK_JARS_DIR}/hadoop-aws-3.3.4.jar \
        https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar && \
    curl -fSL -o ${SPARK_JARS_DIR}/aws-java-sdk-bundle-1.12.262.jar \
        https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Default command (can be overridden in docker-compose)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
