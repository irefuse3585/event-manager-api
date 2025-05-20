# Stage 1: install dependencies in a slim builder image
FROM python:3.10-slim-bullseye AS builder

WORKDIR /app

# Copy and install runtime dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (optional for wheels; здесь для completeness)
COPY . .

# Stage 2: runtime image
FROM python:3.10-slim-bullseye

WORKDIR /app

# Copy entire /usr/local (bin + lib) from the builder
COPY --from=builder /usr/local /usr/local

# Copy application code
COPY --from=builder /app /app

# Expose FastAPI port
EXPOSE 8000

# Launch FastAPI via Uvicorn
ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
