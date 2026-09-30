"""Model loading: from the MLflow registry (by alias) or from a local bundle directory."""

from __future__ import annotations

import json
import logging
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path

from threadline.bundle import Recommender

from app.settings import Settings

log = logging.getLogger(__name__)


def _find_bundle(root: Path) -> Path:
    for p in root.rglob("metadata.json"):
        if (p.parent / "ranker.joblib").exists():
            return p.parent
    raise FileNotFoundError(f"No model bundle under {root}")


def resolve_bundle(s: Settings) -> tuple[Path, dict]:
    """Return (bundle directory, registry info)."""
    if s.model_uri:
        import mlflow

        if s.mlflow_tracking_uri:
            mlflow.set_tracking_uri(s.mlflow_tracking_uri)
        info: dict = {"model_uri": s.model_uri}
        if s.model_uri.startswith("models:/") and "@" in s.model_uri:
            name, alias = s.model_uri.removeprefix("models:/").split("@", 1)
            mv = mlflow.MlflowClient().get_model_version_by_alias(name, alias)
            info.update(version=mv.version, alias=alias, run_id=mv.run_id)
        target = Path(tempfile.mkdtemp(prefix="model-"))
        local = mlflow.artifacts.download_artifacts(artifact_uri=s.model_uri, dst_path=str(target))
        return _find_bundle(Path(local)), info
    return _find_bundle(Path(s.bundle_dir)), {"model_uri": f"file:{s.bundle_dir}", "version": "local"}


@dataclass
class ModelState:
    recommender: Recommender | None = None
    info: dict = field(default_factory=dict)
    error: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def load(self, s: Settings) -> None:
        """Load (or hot-swap) the model. On failure keep serving the previous one."""
        try:
            path, info = resolve_bundle(s)
            rec = Recommender(path)
            info["load_seconds"] = round(rec.load_seconds, 3)
            with self.lock:
                self.recommender, self.info, self.error = rec, info, None
            log.info("Model ready: %s", json.dumps(info))
        except Exception as e:  # keep the process up; /health reports the problem
            log.exception("Model load failed")
            self.error = f"{type(e).__name__}: {e}"

    @property
    def version(self) -> str:
        return str(self.info.get("version", "none"))
