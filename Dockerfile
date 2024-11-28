# Dockerfile for building a docker image for bkpmgt_srvr

# sudo docker build -t bkpmgt_srvr .

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

# Copy the 'srvr' directory into the container
COPY srvr /app/srvr

# Expose the port the app will run on
EXPOSE 5000

# Run the application using Uvicorn, inside the virtual environment
CMD ["uvicorn", "srvr.srvr:app", "--host", "0.0.0.0", "--port", "5000"]