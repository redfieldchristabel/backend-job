# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:///kakitangan.db

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY docker_entry.sh /app/docker_entry.sh

RUN chmod +x /app/docker_entry.sh

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application using uvicorn
CMD ["/app/docker_entry.sh"]