# Start from a lightweight Python Alpine base
FROM python:3.12-alpine

# Update and upgrade Alpine packages
RUN apk --no-cache update && \
    apk --no-cache upgrade

# Create a non-root user and group
RUN addgroup -S appuser && adduser -S -u 1000 -G appuser appuser && mkdir /app
RUN mkdir /data
# Set the working directory
WORKDIR /app

# Copy your application file into the container
COPY quickguard.py /app/

# Adjust ownership so our non-root user can run everything
RUN chown -R appuser:appuser /app
RUN chown -R appuser:appuser /data
# Switch to non-root user
USER appuser

# By default, run quickguard.py from the virtual environment
ENTRYPOINT ["python", "quickguard.py"]
