FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
        libgl1-mesa-glx \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        cmake \
        build-essential \
        ffmpeg \
        libxrender1 \
        wget \
        && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY app/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir dlib
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY app/ .

# Create necessary directories
RUN mkdir -p database attendance_logs

# Set permissions
RUN chmod -R 755 .

# Expose port
EXPOSE 5000

# Command to run the application
CMD ["python", "mapp.py"]