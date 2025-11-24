# Use slim Python image
FROM python:3.12-slim

# Set workdir
WORKDIR /app

# Copy API code
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir fastapi uvicorn[standard] pydantic pandas requests python-dotenv

# Ensure parent folder is on PYTHONPATH so WeatherImpact can be imported when present
ENV PYTHONPATH=/app/..:$PYTHONPATH

# Expose port (Railway provides PORT env)
EXPOSE 8000

# Run the app (shell form so ${PORT} expands on Railway)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}


