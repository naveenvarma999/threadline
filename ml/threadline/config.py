"""Central configuration. Every value can be overridden with an environment variable."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _env_path(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default)))


@dataclass(frozen=True)
class Paths:
    raw_hm: Path = field(default_factory=lambda: _env_path("TL_RAW_HM_DIR", REPO_ROOT / "data" / "raw" / "hm"))
    processed: Path = field(default_factory=lambda: _env_path("TL_PROCESSED_DIR", REPO_ROOT / "data" / "processed"))
    artifacts: Path = field(default_factory=lambda: _env_path("TL_ARTIFACTS_DIR", REPO_ROOT / "artifacts"))


@dataclass(frozen=True)
class TrainConfig:
    # How many trailing weeks of transactions to keep (keeps the full H&M set laptop-sized).
    history_weeks: int = int(os.environ.get("TL_HISTORY_WEEKS", 16))
    # Random sample of active customers to keep (0 = all). Keeps real H&M runs within laptop RAM
    # and keeps the serving bundle small enough for a 2 GB server.
    max_customers: int = int(os.environ.get("TL_MAX_CUSTOMERS", 0))
    # Label weeks used to train the ranker, counted back from the validation week.
    ranker_train_weeks: int = int(os.environ.get("TL_RANKER_TRAIN_WEEKS", 3))
    k: int = 12  # H&M metric is MAP@12
    # Candidate budget per retriever.
    n_popular: int = 30
    n_repurchase: int = 20
    n_cooc: int = 40
    n_two_tower: int = 50
    # Two-tower
    tt_dim: int = 64
    tt_epochs: int = int(os.environ.get("TL_TT_EPOCHS", 4))
    tt_batch: int = 1024
    tt_lr: float = 2e-3
    tt_history_len: int = 20
    # Content embedding (TensorFlow)
    content_dim: int = 32
    content_epochs: int = int(os.environ.get("TL_CONTENT_EPOCHS", 15))
    seed: int = 42


MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", f"sqlite:///{REPO_ROOT / 'mlflow.db'}")
MLFLOW_EXPERIMENT = os.environ.get("MLFLOW_EXPERIMENT", "threadline")
REGISTERED_MODEL = os.environ.get("TL_REGISTERED_MODEL", "threadline-recommender")
