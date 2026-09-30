"""End-to-end training pipeline.

    python -m threadline.train                 # synthetic data unless data/raw/hm/*.csv exists
    python -m threadline.train --source hm     # force real H&M data

Time layout (T = last week in the data, R = ranker label weeks):

    evaluation run   retrievers: weeks < T-R-1   ranker labels: T-R-1 .. T-2   validation: T-1   test: T
    production refit retrievers: weeks < T-R+1   ranker labels: T-R+1 .. T     serves week T+1

Retrievers are always trained on data strictly before every ranker label week, so the
ranker never sees retrieval scores that were fitted on its own labels.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd

from threadline import ranker as rk
from threadline.bundle import save_bundle
from threadline.config import MLFLOW_EXPERIMENT, MLFLOW_TRACKING_URI, REGISTERED_MODEL, Paths, TrainConfig
from threadline.data import Dataset, build_dataset
from threadline.features import FEATURES, build_features, make_snapshot
from threadline.metrics import catalogue_coverage, map_at_k, recall_at_k
from threadline.retrieval import CandidateConfig, CandidateGenerator, RetrievalModels, build_cooccurrence
from threadline.two_tower import train_two_tower

log = logging.getLogger("threadline.train")
DEEP_FEATURES = ["src_tt", "rank_tt", "tt_score", "content_sim"]


def content_embeddings_subprocess(paths: Paths) -> np.ndarray:
    """Train the Keras content model in a child process (TF and PyTorch conflict in one process)."""
    out = paths.artifacts / "content_emb.npy"
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    subprocess.run([sys.executable, "-m", "threadline.content", "--out", str(out)], check=True)
    log.info("Content embeddings trained in %.1fs", time.perf_counter() - t0)
    return np.load(out)


def fit_retrievers(
    ds: Dataset, cutoff_week: int, content_emb: np.ndarray, cfg: TrainConfig, log_fn=None
) -> RetrievalModels:
    tx = ds.transactions[ds.transactions["week"] < cutoff_week]
    t0 = time.perf_counter()
    tt = train_two_tower(tx, ds.articles, ds.customers, content_emb, dim=cfg.tt_dim, epochs=cfg.tt_epochs,
                         batch_size=cfg.tt_batch, lr=cfg.tt_lr, hist_len=cfg.tt_history_len, seed=cfg.seed,
                         log_fn=log_fn)
    log.info("Two-tower trained in %.1fs", time.perf_counter() - t0)
    cooc = build_cooccurrence(tx[tx["week"] >= cutoff_week - 8])
    return RetrievalModels(tt, content_emb, cooc, ds.articles["article_id"].to_numpy())


def label_week_data(
    ds: Dataset, week: int, gen: CandidateGenerator, max_users: int, seed: int
) -> tuple[pd.DataFrame, dict]:
    """Candidates + features + labels for the customers who bought something in ``week``."""
    snap = make_snapshot(ds, week)
    bought = ds.transactions[ds.transactions["week"] == week]
    actual = bought.groupby("customer_idx")["article_id"].apply(lambda s: list(dict.fromkeys(s))).to_dict()
    users = np.array(sorted(actual))
    if len(users) > max_users:
        users = np.sort(np.random.default_rng(seed + week).choice(users, size=max_users, replace=False))
        actual = {u: actual[u] for u in users}
    cands = gen.generate(users, snap)
    feats = build_features(cands, snap)
    pos = set(zip(bought["customer_idx"], bought["article_id"]))
    feats["label"] = np.fromiter((p in pos for p in zip(feats["customer_idx"], feats["article_id"])),
                                 dtype=np.int8, count=len(feats))
    feats["week"] = week
    log.info("week %d: %d users, %d candidates, %.2f%% positive",
             week, len(users), len(feats), 100 * feats["label"].mean())
    return feats, actual


def evaluate(model, df: pd.DataFrame, actual: dict, n_items: int, k: int) -> dict[str, float]:
    pred = rk.top_k(df, rk.score(model, df), k)
    all_cands = df.groupby("customer_idx")["article_id"].apply(list).to_dict()
    return {
        f"map{k}": map_at_k(actual, pred, k),
        f"recall{k}": recall_at_k(actual, pred, k),
        "candidate_recall": recall_at_k(actual, all_cands),
        "coverage": catalogue_coverage(pred, n_items, k),
        "auc": rk.auc(model, df),
    }


def baselines(gen: CandidateGenerator, df: pd.DataFrame, actual: dict, k: int) -> dict[str, float]:
    return {f"baseline_{s}_map{k}": map_at_k(actual, gen.source_ranking(df, s, k), k)
            for s in ("pop", "rep", "cooc", "tt")}


def build_ranker_training(ds, weeks, gen, cfg, max_users):
    parts = [label_week_data(ds, w, gen, max_users, cfg.seed)[0] for w in weeks]
    return pd.concat(parts, ignore_index=True)


def run(args: argparse.Namespace) -> dict:
    cfg, paths = TrainConfig(), Paths()
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT)

    ds, source = build_dataset(paths, cfg, source=args.source)
    T, R, k = ds.last_week, cfg.ranker_train_weeks, cfg.k
    cand_cfg = CandidateConfig(cfg.n_popular, cfg.n_repurchase, cfg.n_cooc, cfg.n_two_tower)
    customer_age = ds.customers.set_index("customer_idx")["age"]

    with mlflow.start_run(run_name=f"{source}-T{T}") as run:
        mlflow.set_tags({"data_source": source, "stage": "two-stage recommender"})
        mlflow.log_params({
            "data_source": source, "n_transactions": len(ds.transactions), "n_articles": len(ds.articles),
            "n_customers": len(ds.customers), "history_weeks": cfg.history_weeks, "ranker_label_weeks": R,
            "tt_dim": cfg.tt_dim, "tt_epochs": cfg.tt_epochs, "tt_lr": cfg.tt_lr, "content_dim": cfg.content_dim,
            **{f"n_{n}": v for n, v in vars(cand_cfg).items()},
        })
        step_log = lambda name, v, step: mlflow.log_metric(name, v, step=step)  # noqa: E731

        # 1. Content embeddings (TensorFlow): article metadata only, no time leakage.
        content_emb = content_embeddings_subprocess(paths)
        mlflow.log_metric("content_emb_dim", content_emb.shape[1])

        # 2. Evaluation run
        eval_cut = T - R - 1
        retr = fit_retrievers(ds, eval_cut, content_emb, cfg, log_fn=step_log)
        gen = CandidateGenerator(retr, customer_age, cand_cfg)
        train_df = build_ranker_training(ds, range(eval_cut, T - 1), gen, cfg, args.max_users)
        val_df, val_actual = label_week_data(ds, T - 1, gen, args.max_users, cfg.seed)
        test_df, test_actual = label_week_data(ds, T, gen, args.max_users, cfg.seed)

        t0 = time.perf_counter()
        model = rk.train_ranker(train_df, seed=cfg.seed)
        mlflow.log_metric("ranker_train_seconds", time.perf_counter() - t0)
        val = evaluate(model, val_df, val_actual, len(ds.articles), k)
        test = evaluate(model, test_df, test_actual, len(ds.articles), k)
        mlflow.log_metrics({f"val_{m}": v for m, v in val.items()})
        mlflow.log_metrics({f"test_{m}": v for m, v in test.items()})
        base = baselines(gen, test_df, test_actual, k)
        mlflow.log_metrics({f"test_{m}": v for m, v in base.items()})

        # Ablation: same ranker without the deep-learning signals.
        shallow_feats = [f for f in FEATURES if f not in DEEP_FEATURES]
        shallow = rk.train_ranker(train_df, seed=cfg.seed, features=shallow_feats)
        abl = evaluate(shallow, test_df, test_actual, len(ds.articles), k)
        mlflow.log_metric(f"test_no_deep_features_map{k}", abl[f"map{k}"])

        imp = rk.importance(model, val_df)
        ablation = {
            "popularity baseline": base[f"baseline_pop_map{k}"],
            "repurchase only": base[f"baseline_rep_map{k}"],
            "co-purchase only": base[f"baseline_cooc_map{k}"],
            "two-tower only": base[f"baseline_tt_map{k}"],
            "ranker without deep features": abl[f"map{k}"],
            "full ranker": test[f"map{k}"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            imp.to_csv(tmp / "feature_importance.csv", header=["auc_drop"])
            (tmp / "ablation.json").write_text(json.dumps(ablation, indent=2))
            mlflow.log_artifacts(str(tmp), artifact_path="evaluation")
        log.info("TEST  %s", json.dumps({k_: round(v, 4) for k_, v in test.items()}))
        log.info("ABLATION %s", json.dumps({k_: round(v, 4) for k_, v in ablation.items()}))

        # 3. Production refit on the most recent weeks.
        if args.no_refit:
            prod_retr, prod_model = retr, model
        else:
            prod_cut = T - R + 1
            prod_retr = fit_retrievers(ds, prod_cut, content_emb, cfg)
            prod_gen = CandidateGenerator(prod_retr, customer_age, cand_cfg)
            prod_train = build_ranker_training(ds, range(prod_cut, T + 1), prod_gen, cfg, args.max_users)
            prod_model = rk.train_ranker(prod_train, seed=cfg.seed)
        serve_snap = make_snapshot(ds, T + 1)

        metadata = {
            "model_name": REGISTERED_MODEL, "run_id": run.info.run_id, "data_source": source,
            "created_at": pd.Timestamp.utcnow().isoformat(), "serves_from": str(serve_snap.ref_date.date()),
            "metrics": {f"test_{m}": v for m, v in {**test, **base}.items()}, "ablation": ablation,
            "features": FEATURES, "top_features": imp.head(10).round(5).to_dict(),
        }
        bundle_dir = paths.artifacts / "bundle"
        if bundle_dir.exists():
            shutil.rmtree(bundle_dir)
        save_bundle(bundle_dir, articles=ds.articles, customers=ds.customers, snapshot=serve_snap,
                    retrieval=prod_retr, ranker=prod_model, metadata=metadata)
        log.info("Bundle written to %s", bundle_dir)

        if not args.no_register:
            from threadline.registry import log_and_register

            version = log_and_register(bundle_dir, test[f"map{k}"])
            metadata["registered_version"] = version
            if args.auto_promote:
                from threadline.registry import promote_if_better

                promote_if_better(version)
        return {"test": test, "ablation": ablation, "run_id": run.info.run_id}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", choices=["auto", "synthetic", "hm"], default="auto")
    p.add_argument("--max-users", type=int, default=20000, help="cap on customers per label week")
    p.add_argument("--no-refit", action="store_true", help="ship the evaluation models instead of refitting")
    p.add_argument("--no-register", action="store_true", help="skip MLflow model registry")
    p.add_argument("--auto-promote", action="store_true", help="promote to champion if it beats the current one")
    run(p.parse_args())


if __name__ == "__main__":
    main()
