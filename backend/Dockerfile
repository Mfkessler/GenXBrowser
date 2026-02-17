# =============================================================================
# GenXBrowser H5AD Backend - Dockerfile
# =============================================================================
# Flask backend that reads from H5AD files.
# h5ad-lib is inlined — no external dependency needed.
# =============================================================================

FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libhdf5-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (cacheable layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application + inlined h5ad_lib
COPY h5ad_lib/ ./h5ad_lib/
COPY app/ ./app/
COPY gunicorn.conf.py run.py ./

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:5000/health || exit 1

CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:create_app()"]
