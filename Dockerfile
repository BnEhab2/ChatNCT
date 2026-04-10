FROM python:3.11-slim

# Set up user to run the app as Hugging Face requires non-root user
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Install system dependencies needed for OpenCV and MediaPipe
USER root
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgles2 \
    && rm -rf /var/lib/apt/lists/*
USER user

# Copy requirements first to leverage Docker cache
COPY --chown=user requirments.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY --chown=user . .

# Hugging Face Spaces expect apps to run on port 7860
ENV PORT=7860
EXPOSE 7860

# Run the production server
CMD ["python", "run_production.py"]
