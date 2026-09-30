"""MLflow pyfunc wrapper so the bundle can be logged, registered and loaded by alias."""

from __future__ import annotations

from pathlib import Path

import mlflow.pyfunc
import pandas as pd


class ThreadlinePyfunc(mlflow.pyfunc.PythonModel):
    """Input: DataFrame with ``customer_id`` (and optional ``k``). Output: one row per recommendation."""

    def load_context(self, context) -> None:
        from threadline.bundle import Recommender

        self.rec = Recommender(Path(context.artifacts["bundle"]))

    def predict(self, context, model_input: pd.DataFrame, params=None) -> pd.DataFrame:
        rows = []
        for r in model_input.itertuples(index=False):
            k = int(getattr(r, "k", 12) or 12)
            for rank, rec in enumerate(self.rec.recommend(str(r.customer_id), k=k)):
                rows.append({"customer_id": r.customer_id, "rank": rank, "article_id": rec.article_id,
                             "score": rec.score, "reason": rec.reason})
        return pd.DataFrame(rows)
