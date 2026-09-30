# Training image: CPU PyTorch + TensorFlow + MLflow. Build from the repository root.
#   docker build -f ml/Dockerfile -t threadline-trainer .
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 TF_CPP_MIN_LOG_LEVEL=2
WORKDIR /app
RUN pip install torch==2.14.0 --index-url https://download.pytorch.org/whl/cpu
COPY ml/pyproject.toml ml/pyproject.toml
COPY ml/threadline ml/threadline
RUN pip install "./ml[train]" boto3
COPY ml/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
