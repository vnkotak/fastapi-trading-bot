# Start with official Python image
FROM python:3.10-slim

# Install system dependencies for TA-Lib
RUN apt-get update && apt-get install -y \
    build-essential \
    libta-lib0 \
    libta-lib-dev \
    gcc \
 && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy all files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Command to run your app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
