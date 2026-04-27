FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Cloud Run injects PORT; default to 8080
ENV PORT=8080

# Use gunicorn with the Flask server exposed by Dash
CMD exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120
