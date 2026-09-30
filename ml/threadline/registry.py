"""MLflow model registry helpers: register a bundle, gate promotion, list versions.

    python -m threadline.registry list
    python -m threadline.registry promote --version 3         # manual promotion
    python -m threadline.registry promote --version 3 --gate  # only if it beats the champion
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import mlflow
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException

from threadline.config import MLFLOW_TRACKING_URI, REGISTERED_MODEL

log = logging.getLogger(__name__)
CHAMPION, CHALLENGER = "champion", "challenger"
METRIC = "test_map12"
# Challenger must beat champion by 1% relative MAP@12 to be promoted automatically.
MIN_RELATIVE_GAIN = 0.01

PKG_DIR = Path(__file__).resolve().parent


def client() -> MlflowClient:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    return MlflowClient()


def log_and_register(bundle_dir: Path, map12: float) -> str:
    """Log the bundle as a pyfunc model in the active run, register it and alias it ``challenger``."""
    from threadline.mlflow_model import ThreadlinePyfunc

    info = mlflow.pyfunc.log_model(
        name="recommender",
        python_model=ThreadlinePyfunc(),
        artifacts={"bundle": str(bundle_dir)},
        code_paths=[str(PKG_DIR)],
        pip_requirements=["numpy", "pandas", "pyarrow", "scikit-learn", "joblib", "faiss-cpu"],
        registered_model_name=REGISTERED_MODEL,
    )
    version = str(info.registered_model_version)
    c = client()
    c.set_model_version_tag(REGISTERED_MODEL, version, METRIC, f"{map12:.6f}")
    c.set_registered_model_alias(REGISTERED_MODEL, CHALLENGER, version)
    log.info("Registered %s version %s as %s", REGISTERED_MODEL, version, CHALLENGER)
    return version


def _metric(c: MlflowClient, version: str) -> float:
    mv = c.get_model_version(REGISTERED_MODEL, version)
    return float(mv.tags.get(METRIC, "nan"))


def promote_if_better(version: str) -> bool:
    c = client()
    new = _metric(c, version)
    try:
        champ = c.get_model_version_by_alias(REGISTERED_MODEL, CHAMPION)
    except MlflowException:
        champ = None
    if champ is None:
        decision, reason = True, "no champion yet"
    else:
        old = _metric(c, champ.version)
        decision = new >= old * (1 + MIN_RELATIVE_GAIN)
        reason = f"challenger {new:.5f} vs champion {old:.5f} (needs +{MIN_RELATIVE_GAIN:.0%})"
    log.info("Promotion gate for version %s: %s -> %s", version, reason, "PROMOTE" if decision else "KEEP")
    if decision:
        promote(version)
    return decision


def promote(version: str) -> None:
    client().set_registered_model_alias(REGISTERED_MODEL, CHAMPION, version)
    log.info("Version %s is now %s", version, CHAMPION)


def list_versions() -> list[dict]:
    c = client()
    out = []
    for found in c.search_model_versions(f"name='{REGISTERED_MODEL}'"):
        mv = c.get_model_version(REGISTERED_MODEL, found.version)  # search results omit aliases
        out.append({
            "version": mv.version, "aliases": list(mv.aliases), "run_id": mv.run_id,
            "created": mv.creation_timestamp, METRIC: mv.tags.get(METRIC),
        })
    return sorted(out, key=lambda r: int(r["version"]), reverse=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    pr = sub.add_parser("promote")
    pr.add_argument("--version", required=True)
    pr.add_argument("--gate", action="store_true")
    a = p.parse_args()
    if a.cmd == "list":
        for row in list_versions():
            print(row)
    elif a.gate:
        promote_if_better(a.version)
    else:
        promote(a.version)


if __name__ == "__main__":
    main()
