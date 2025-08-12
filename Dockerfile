# Base Dockerfile template for all microservices
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Ensure requirements.txt gets copied from build context root of docker-compose
COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy service source (current service context)
# Ensure templates directory for policy_engine is included during build
COPY . .

# Expose port from env or default
ARG PORT=8000
ENV PORT=${PORT}

# Entrypoint - run with Uvicorn
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]