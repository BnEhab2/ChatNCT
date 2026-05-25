FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port 7860 (HF Spaces default)
EXPOSE 7860

# Run app.py which starts BOTH servers:
#   - Attendance server (port 5001) in a background thread
#   - Main server (port 7860) in the main thread
CMD ["python", "app.py"]
