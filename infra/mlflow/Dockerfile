# MLflow tracking server + model registry. Backend: Postgres. Artifacts: S3 (or a local volume).
FROM python:3.11-slim
ENV PIP_NO_CACHE_DIR=1
RUN pip install mlflow==3.16.1 "psycopg2-binary==2.9.13" boto3==1.43.105
COPY start.sh /start.sh
RUN chmod +x /start.sh
EXPOSE 5000
CMD ["/start.sh"]
