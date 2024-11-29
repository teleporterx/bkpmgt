# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the pyproject.toml and poetry.lock files first to leverage Docker cache
COPY pyproject.toml poetry.lock /app/

# Install Poetry and create a virtual environment, then install dependencies
RUN python -m venv .venv && \
    . .venv/bin/activate && \
    pip install --upgrade pip && \
    pip install poetry && \
    poetry install --no-dev

# Set environment variables for the virtual environment
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Set default values for RabbitMQ and MongoDB host (this can be overridden in docker-compose or environment files)
ENV RABBITMQ_HOST=rabbitmq
ENV MONGO_HOST=mongoose
# Set the RESTIC_PATH environment variable to the correct directory
ENV RESTIC_PATH=/app/srvr/backup_recovery

# Copy the 'srvr' directory into the container
COPY srvr /app/srvr

# Install wget and bzip2 to download and extract Restic
RUN apt-get update && \
    apt-get install -y wget bzip2 && \
    wget https://github.com/restic/restic/releases/download/v0.17.3/restic_0.17.3_linux_amd64.bz2 -P /app/srvr/backup_recovery/ && \
    bunzip2 /app/srvr/backup_recovery/restic_0.17.3_linux_amd64.bz2 && \
    mv /app/srvr/backup_recovery/restic_0.17.3_linux_amd64 /app/srvr/backup_recovery/restic && \
    chmod +x /app/srvr/backup_recovery/restic

# Expose the port the app will run on
EXPOSE 5000

# Run the application using Uvicorn, inside the virtual environment
CMD ["uvicorn", "srvr.srvr:app", "--host", "0.0.0.0", "--port", "5000"]