FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
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

# Run the Flask app on port 7860
CMD ["python", "-c", "from server import app; app.run(host='0.0.0.0', port=7860, debug=False)"]
