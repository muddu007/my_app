FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Runtime environment variables (override with -e at docker run time)
#ENV API_GATEWAY_URL=""
#    API_KEY="" \
#    REQUEST_TIMEOUT=30 \
#    FLASK_DEBUG=true

# Expose Flask port
EXPOSE 5000

# Use gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "app:app"]
