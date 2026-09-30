"""Runtime settings, read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Where to load the model from. MODEL_URI wins when set (e.g. models:/threadline-recommender@champion).
    model_uri: str = os.environ.get("MODEL_URI", "")
    bundle_dir: str = os.environ.get("BUNDLE_DIR", "/app/artifacts/bundle")
    mlflow_tracking_uri: str = os.environ.get("MLFLOW_TRACKING_URI", "")
    redis_url: str = os.environ.get("REDIS_URL", "")
    cache_ttl_seconds: int = int(os.environ.get("CACHE_TTL_SECONDS", "300"))
    admin_token: str = os.environ.get("INFERENCE_ADMIN_TOKEN", "change-me")
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")


settings = Settings()
