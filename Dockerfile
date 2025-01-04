# Use the Alpine image as the base image
FROM python:3.9-alpine


# Install system dependencies including ffmpeg, build tools, and Python dependencies
RUN apk update && \
    apk add --no-cache \
    ffmpeg \
    build-base \
    python3-dev \
    libsndfile \
    curl \
    bash \
    libmagic \
    ca-certificates && \
    apk add --no-cache --virtual .build-deps \
    gcc \
    musl-dev \
    libffi-dev && \
    pip3 install --upgrade pip && \
    apk del .build-deps

# Set the working directory in the container
WORKDIR /app

# Copy only requirements.txt to cache dependencies
COPY requirements.txt /app/

# Install Python dependencies from requirements.txt
RUN pip install -r requirements.txt

# Copy the rest of the application files
COPY . /app

# Copy the robots.txt to the static folder
COPY static/robots.txt static/

# Set environment variable to indicate Flask app is running in production mode
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Expose the port that Flask runs on
EXPOSE 8080

# Set the command to run the Flask app
CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]
