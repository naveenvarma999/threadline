# Build from the repository root:  docker build -f services/inference/Dockerfile -t threadline-inference .
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# Shared feature/serving code (no PyTorch or TensorFlow: serving is NumPy + scikit-learn only)
COPY ml/pyproject.toml ml/pyproject.toml
COPY ml/threadline ml/threadline
RUN pip install ./ml

COPY services/inference/requirements.txt .
RUN pip install -r requirements.txt

COPY services/inference/app app
RUN useradd --create-home --uid 10001 app && mkdir -p /app/artifacts && chown -R app /app
USER app

EXPOSE 8001
HEALTHCHECK --interval=15s --timeout=3s --start-period=60s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8001/health').status==200 else 1)"
# Two workers per task: scoring is CPU-bound and each worker holds its own copy of the model.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2", "--no-access-log"]
