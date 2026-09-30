#!/bin/sh
# BACKEND_STORE_URI    postgresql://user:pass@host:5432/mlflow
# ARTIFACTS_DESTINATION s3://bucket/mlflow  (or /mlartifacts for a local volume)
set -e
python - <<'EOF'
# Create the mlflow database on first start (RDS only creates the default one).
import os, urllib.parse, psycopg2
u = urllib.parse.urlparse(os.environ["BACKEND_STORE_URI"])
db = u.path.lstrip("/")
conn = psycopg2.connect(host=u.hostname, port=u.port or 5432, user=u.username, password=urllib.parse.unquote(u.password or ""), dbname="postgres")
conn.autocommit = True
with conn.cursor() as c:
    c.execute("SELECT 1 FROM pg_database WHERE datname=%s", (db,))
    if not c.fetchone():
        c.execute(f'CREATE DATABASE "{db}"')
        print("Created database", db)
EOF
exec mlflow server \
  --backend-store-uri "$BACKEND_STORE_URI" \
  --artifacts-destination "${ARTIFACTS_DESTINATION:-/mlartifacts}" \
  --serve-artifacts \
  --host 0.0.0.0 --port 5000 \
  --allowed-hosts "${MLFLOW_ALLOWED_HOSTS:-*}"
