# ─── VIGIL UI — Dockerfile ────────────────────────────────────────────────────
#
# Lightweight Streamlit container.
# Kept intentionally separate from the API Dockerfile so that:
#   - UI rebuild doesn't trigger API rebuild (and vice-versa)
#   - Dependencies stay minimal (no FastAPI/asyncpg/etc.)

FROM python:3.11-slim

WORKDIR /app

# Install only UI dependencies — much smaller layer than the API image
COPY ui/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy UI source (mounted as a volume in dev so edits reflect instantly)
COPY ui/ ./ui/

# Streamlit listens on 8501 by default
EXPOSE 8501

# --server.address 0.0.0.0  — listen on all interfaces (required inside Docker)
# --server.headless true     — suppress the "Do you want to receive updates?" prompt
# --server.fileWatcherType none — disable inotify watcher (saves resources in Docker)
CMD ["streamlit", "run", "ui/app.py", "--server.port", "8501", "--server.address", "0.0.0.0", "--server.headless", "true", "--server.fileWatcherType", "none"]
