FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required for PDF parsing and OCR
RUN apt-get update && apt-get install -y \
    build-essential \
    tesseract-ocr \
    libpoppler-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories to avoid permission errors
RUN mkdir -p data uploads chroma_db logs

# Expose standard Streamlit port
EXPOSE 8501

# Start the Streamlit application with CORS and XSRF disabled to fix Render proxy WebSocket errors
CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0", "--server.enableCORS", "false", "--server.enableXsrfProtection", "false"]
