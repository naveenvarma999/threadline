#!/bin/sh
# Training job entrypoint (local Compose or a scheduled ECS task).
#   DATA_S3_URI       optional s3://bucket/prefix with raw H&M CSVs (articles.csv, customers.csv, transactions_train.csv)
#   PROCESSED_S3_URI  optional s3://bucket/prefix to publish processed Parquet for the shop API seed
set -e
if [ -n "$DATA_S3_URI" ]; then
  python - <<'EOF'
import os, boto3
bucket, _, prefix = os.environ["DATA_S3_URI"][5:].partition("/")
dst = os.environ.get("TL_RAW_HM_DIR", "/app/data/raw/hm")
os.makedirs(dst, exist_ok=True)
s3 = boto3.client("s3")
for name in ("articles.csv", "customers.csv", "transactions_train.csv"):
    s3.download_file(bucket, f"{prefix.rstrip('/')}/{name}", os.path.join(dst, name))
print("Downloaded raw data to", dst)
EOF
fi

python -m threadline.train --auto-promote "$@"

if [ -n "$PROCESSED_S3_URI" ]; then
  python - <<'EOF'
import os, boto3
from threadline.config import Paths
bucket, _, prefix = os.environ["PROCESSED_S3_URI"][5:].partition("/")
s3 = boto3.client("s3")
for p in Paths().processed.glob("*.parquet"):
    s3.upload_file(str(p), bucket, f"{prefix.rstrip('/')}/{p.name}")
print("Published processed data to", os.environ["PROCESSED_S3_URI"])
EOF
fi

# Tell the running inference service to pick up a newly promoted champion.
if [ -n "$INFERENCE_RELOAD_URL" ]; then
  python -c "import os,urllib.request as u; r=u.Request(os.environ['INFERENCE_RELOAD_URL'],method='POST',headers={'x-admin-token':os.environ.get('INFERENCE_ADMIN_TOKEN','')}); print(u.urlopen(r,timeout=120).read().decode())" || true
fi
