FROM python:3.12-slim

WORKDIR /app

# Install uv for dependency management
RUN pip install --no-cache-dir uv

# Copy dependency metadata and install (cached)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy project files
COPY . .

EXPOSE 8000

# Start FastAPI app
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
