FROM python:3.10-slim as builder

WORKDIR /app
COPY pyproject.toml .
# Create a dummy src so install works if we use pip install .
RUN mkdir src && touch src/__init__.py
RUN pip wheel --no-cache-dir --wheel-dir /usr/src/app/wheels .

FROM python:3.10-slim

# Create a non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy built wheels from builder and install
COPY --from=builder /usr/src/app/wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Copy application source code
COPY src/ ./src/

# Change ownership
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
