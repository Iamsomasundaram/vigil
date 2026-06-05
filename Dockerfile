# ─── VIGIL — Dockerfile ───────────────────────────────────────────────────────
#
# Multi-stage build:
#   Stage 1 (deps)  — install Python dependencies (cached separately)
#   Stage 2 (final) — copy source and run
#
# This keeps rebuilds fast: changing source code doesn't reinstall packages.

# ── Stage 1: Install dependencies ─────────────────────────────────────────────
FROM python:3.11-slim AS deps

WORKDIR /app

# Copy only the dependency manifest first.
# Docker caches this layer — packages are only reinstalled when
# pyproject.toml changes, not every time source code changes.
COPY pyproject.toml .

# Create a minimal package stub so `pip install -e .` works without full source
RUN mkdir -p vigil && touch vigil/__init__.py

RUN pip install --no-cache-dir ".[api]"


# ── Stage 2: Runtime ───────────────────────────────────────────────────────────
FROM python:3.11-slim AS final

WORKDIR /app

# Copy installed packages from the deps stage
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copy source code
COPY vigil/   ./vigil/
COPY levels/  ./levels/
COPY data/    ./data/

# FastAPI on port 8000
EXPOSE 8000

# --reload makes code changes reflect without rebuilding (for dev)
CMD ["uvicorn", "vigil.api:app", "--host", "0.0.0.0", "--port", "8000"]
