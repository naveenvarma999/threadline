#!/bin/sh
# Container entrypoint: migrate, optionally seed, then serve with gunicorn.
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput >/dev/null

# Seed the catalogue once. SEED_FROM is a local folder or an s3://bucket/prefix holding the
# processed Parquet files written by the training pipeline.
if [ -n "$SEED_FROM" ]; then
  # A failed seed (e.g. no training run has published data yet) must not stop the API.
  if ! python - <<'EOF'
import os, subprocess, sys, tempfile
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from shop.models import Article
if Article.objects.exists():
    print("Catalogue already loaded; skipping seed"); sys.exit(0)
src = os.environ["SEED_FROM"]
if src.startswith("s3://"):
    import boto3
    bucket, _, prefix = src[5:].partition("/")
    dst = tempfile.mkdtemp()
    s3 = boto3.client("s3")
    for name in ("articles.parquet", "customers.parquet", "transactions.parquet"):
        s3.download_file(bucket, f"{prefix.rstrip('/')}/{name}", os.path.join(dst, name))
    src = dst
subprocess.run([sys.executable, "manage.py", "load_catalog", "--processed-dir", src,
                "--customers", os.environ.get("SEED_CUSTOMERS", "5000")], check=True)
EOF
  then
    echo "Catalogue seed skipped: data not available yet at $SEED_FROM"
  fi
fi

exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers "${GUNICORN_WORKERS:-3}" \
  --timeout 30 --access-logfile - --forwarded-allow-ips '*'
